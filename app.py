from flask import Flask, render_template, jsonify, request
import requests
import time
import re
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import random
import socket
import subprocess
import platform

# Configurações - substitua pelos IPs reais dos seus servidores
MGC_URL = "http://{SEU_IP_VM_MGC}:5000"
AWS_US_URL = "http://{SEU_IP_VM_AWS_US}:5000"  # AWS Norte da Virgínia
AWS_BR_URL = "http://{SEU_IP_VM_AWS_BR}:5000"   # AWS São Paulo

# Configurações de teste melhoradas
TENTATIVAS_PADRAO = 5  # Aumentado para maior precisão
TIMEOUT_PADRAO = 10    # Timeout maior para conexões internacionais
PAUSA_ENTRE_TENTATIVAS = 0.2  # Pausa entre tentativas

app = Flask(__name__)

def medir_latencia(url, timeout=TIMEOUT_PADRAO):
    """Mede a latência de uma URL específica com maior precisão"""
    try:
        # Adiciona um parâmetro aleatório para evitar cache
        cache_buster = f"?t={int(time.time())}&r={random.randint(1000, 9999)}"
        start = time.perf_counter()  # Mais preciso que time.time()
        response = requests.get(f"{url}{cache_buster}", timeout=timeout)
        end = time.perf_counter()
        
        if response.status_code == 200:
            return round((end - start) * 1000, 2)  # Maior precisão (2 casas decimais)
        else:
            return None
    except requests.exceptions.Timeout:
        return "timeout"
    except Exception as e:
        print(f"Erro ao medir latência de {url}: {e}")
        return None

def medir_latencia_avancada(url, tentativas=TENTATIVAS_PADRAO):
    """Mede latência com análise estatística mais robusta"""
    latencias = []
    timeouts = 0
    erros = 0
    
    for i in range(tentativas):
        latencia = medir_latencia(url)
        
        if latencia == "timeout":
            timeouts += 1
        elif latencia is None:
            erros += 1
        else:
            latencias.append(latencia)
        
        if i < tentativas - 1:  # Não fazer pausa na última iteração
            time.sleep(PAUSA_ENTRE_TENTATIVAS)
    
    if not latencias:
        return {
            "media": None,
            "mediana": None,
            "min": None,
            "max": None,
            "desvio_padrao": None,
            "taxa_sucesso": 0,
            "timeouts": timeouts,
            "erros": erros,
            "tentativas": tentativas
        }
    
    return {
        "media": round(statistics.mean(latencias), 2),
        "mediana": round(statistics.median(latencias), 2),
        "min": min(latencias),
        "max": max(latencias),
        "desvio_padrao": round(statistics.stdev(latencias) if len(latencias) > 1 else 0, 2),
        "taxa_sucesso": round((len(latencias) / tentativas) * 100, 1),
        "timeouts": timeouts,
        "erros": erros,
        "tentativas": tentativas,
        "amostras": latencias
    }

def medir_latencia_media(url, tentativas=3):
    """Mantém compatibilidade com a versão anterior"""
    latencias = []
    for _ in range(tentativas):
        latencia = medir_latencia(url)
        if latencia and latencia != "timeout":
            latencias.append(latencia)
        time.sleep(0.1)
    
    if latencias:
        return round(sum(latencias) / len(latencias))
    return None

def ping_servidor(host, timeout=5):
    """Faz ping direto para o servidor (apenas conectividade de rede)"""
    try:
        # Remove http:// e :5000 para obter apenas o IP
        if "://" in host:
            host = host.split("://")[1]
        if ":" in host:
            host = host.split(":")[0]
        
        # Ping dependendo do SO
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", host]
        
        start = time.perf_counter()
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        end = time.perf_counter()
        
        if result.returncode == 0:
            return round((end - start) * 1000, 2)
        return None
    except:
        return None

def testar_conectividade_tcp(host, port, timeout=5):
    """Testa conectividade TCP direta (sem HTTP)"""
    try:
        # Remove protocolo se presente
        if "://" in host:
            host = host.split("://")[1]
        if ":" in host and not host.count(":") > 1:  # IPv4 com porta
            host, _ = host.split(":")
        
        start = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        end = time.perf_counter()
        
        if result == 0:
            return round((end - start) * 1000, 2)
        return None
    except:
        return None

def medir_componentes_separados(url_base):
    """Mede cada componente da latência separadamente"""
    # Extrai host do URL
    if "://" in url_base:
        host = url_base.split("://")[1]
    else:
        host = url_base
    
    if ":" in host:
        host_ip = host.split(":")[0]
        porta = int(host.split(":")[1])
    else:
        host_ip = host
        porta = 80
    
    resultado = {
        "ping_icmp": ping_servidor(host_ip),
        "tcp_connect": testar_conectividade_tcp(host_ip, porta),
        "http_completo": medir_latencia(f"{url_base}/cep/01001000"),
        "health_check": medir_latencia(f"{url_base}/health") if "/health" not in url_base else None
    }
    
    return resultado

@app.route("/")
def home():
    latencia_mgc = medir_latencia_media(f"{MGC_URL}/cep/01001000")
    latencia_aws_us = medir_latencia_media(f"{AWS_US_URL}/cep/01001000")
    latencia_aws_br = medir_latencia_media(f"{AWS_BR_URL}/cep/01001000")

    return render_template("index.html",
                           latencia_mgc=latencia_mgc or "erro",
                           latencia_aws_us=latencia_aws_us or "erro",
                           latencia_aws_br=latencia_aws_br or "erro")

@app.route("/api/latencia")
def api_latencia():
    """API endpoint para obter latência via AJAX"""
    latencia_mgc = medir_latencia_media(f"{MGC_URL}/cep/01001000")
    latencia_aws_us = medir_latencia_media(f"{AWS_US_URL}/cep/01001000")
    latencia_aws_br = medir_latencia_media(f"{AWS_BR_URL}/cep/01001000")
    
    return jsonify({
        "mgc": latencia_mgc,
        "aws_us": latencia_aws_us,
        "aws_br": latencia_aws_br,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/latencia-avancada")
def api_latencia_avancada():
    """API endpoint para análise de latência mais robusta"""
    
    def medir_servidor(nome, url):
        """Função para medir latência de um servidor específico"""
        resultado = medir_latencia_avancada(f"{url}/cep/01001000")
        resultado['servidor'] = nome
        resultado['url'] = url
        return resultado
    
    # Executa medições em paralelo para maior eficiência
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(medir_servidor, "MGC", MGC_URL),
            executor.submit(medir_servidor, "AWS US", AWS_US_URL),
            executor.submit(medir_servidor, "AWS BR", AWS_BR_URL)
        ]
        
        resultados = {}
        for future in futures:
            resultado = future.result()
            nome = resultado['servidor']
            resultados[nome.lower().replace(' ', '_')] = resultado
    
    # Análise comparativa
    medias_validas = {k: v['media'] for k, v in resultados.items() if v['media'] is not None}
    
    if medias_validas:
        melhor_servidor = min(medias_validas.keys(), key=lambda k: medias_validas[k])
        ranking = sorted(medias_validas.items(), key=lambda x: x[1])
    else:
        melhor_servidor = None
        ranking = []
    
    return jsonify({
        "resultados": resultados,
        "analise": {
            "melhor_servidor": melhor_servidor,
            "ranking": ranking,
            "timestamp": datetime.now().isoformat(),
            "total_tentativas": TENTATIVAS_PADRAO
        },
        "metodologia": {
            "tentativas_por_servidor": TENTATIVAS_PADRAO,
            "timeout": TIMEOUT_PADRAO,
            "cache_buster": True,
            "medicao_paralela": True
        }
    })

@app.route("/api/teste-carga")
def api_teste_carga():
    """Endpoint para teste de carga mais intensivo"""
    tentativas = request.args.get('tentativas', 10, type=int)
    tentativas = min(tentativas, 50)  # Limite máximo para não sobrecarregar
    
    def teste_servidor(nome, url):
        return {
            'servidor': nome,
            'resultado': medir_latencia_avancada(f"{url}/cep/01001000", tentativas)
        }
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(teste_servidor, "MGC", MGC_URL),
            executor.submit(teste_servidor, "AWS US", AWS_US_URL),
            executor.submit(teste_servidor, "AWS BR", AWS_BR_URL)
        ]
        
        resultados = [future.result() for future in futures]
    
    return jsonify({
        "resultados": resultados,
        "configuracao": {
            "tentativas": tentativas,
            "timestamp": datetime.now().isoformat()
        }
    })

@app.route("/cep/<cep>")
def consulta_cep(cep):
    # Validação do CEP
    if not re.match(r'^\d{8}$', cep):
        return jsonify({"error": "CEP deve conter exatamente 8 dígitos"}), 400
    
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=10)
        data = resp.json()
        
        # Verifica se o CEP foi encontrado
        if data.get("erro"):
            return jsonify({"error": "CEP não encontrado"}), 404
            
        return jsonify(data)
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout na consulta do CEP"}), 408
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Erro de conexão: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

@app.route("/health")
def health_check():
    """Endpoint de health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route("/dashboard")
def dashboard():
    """Página de dashboard com métricas em tempo real"""
    return render_template("dashboard.html")

@app.route("/graficos")
def graficos():
    """Página com gráficos interativos"""
    return render_template("graficos.html")

@app.route("/comparacao")
def comparacao():
    """Página de comparação detalhada entre VMs"""
    return render_template("comparacao.html")

@app.route("/monitoramento")
def monitoramento():
    """Página de monitoramento em tempo real"""
    return render_template("monitoramento.html")

@app.route("/api/diagnostico-completo")
def api_diagnostico_completo():
    """Diagnóstico completo da arquitetura"""
    
    servidores = {
        "mgc": MGC_URL,
        "aws_us": AWS_US_URL, 
        "aws_br": AWS_BR_URL
    }
    
    diagnostico = {}
    
    for nome, url in servidores.items():
        print(f"🔍 Diagnosticando {nome}...")
        
        componentes = medir_componentes_separados(url)
        
        # Análise dos componentes
        analise = {
            "conectividade_rede": "OK" if componentes["ping_icmp"] else "PROBLEMA",
            "porta_tcp": "OK" if componentes["tcp_connect"] else "PROBLEMA", 
            "servico_http": "OK" if componentes["http_completo"] else "PROBLEMA"
        }
        
        # Identifica gargalos
        gargalos = []
        if componentes["ping_icmp"] and componentes["ping_icmp"] > 200:
            gargalos.append("ALTA_LATENCIA_REDE")
        
        if componentes["tcp_connect"] and componentes["ping_icmp"]:
            tcp_overhead = componentes["tcp_connect"] - componentes["ping_icmp"]
            if tcp_overhead > 100:
                gargalos.append("LENTIDAO_TCP_HANDSHAKE")
        
        if componentes["http_completo"] and componentes["tcp_connect"]:
            http_overhead = componentes["http_completo"] - componentes["tcp_connect"]
            if http_overhead > 500:
                gargalos.append("PROCESSAMENTO_LENTO_SERVIDOR")
        
        diagnostico[nome] = {
            "componentes": componentes,
            "analise": analise,
            "gargalos": gargalos,
            "servidor_url": url
        }
    
    return jsonify({
        "diagnostico": diagnostico,
        "explicacao": {
            "ping_icmp": "Latência pura de rede (seu PC até o servidor)",
            "tcp_connect": "Tempo para estabelecer conexão TCP",
            "http_completo": "Tempo total da requisição HTTP (inclui processamento do servidor + chamada à API externa)",
            "health_check": "Tempo de resposta de endpoint simples (sem chamada externa)"
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/teste-vm-real")
def api_teste_vm_real():
    """Teste usando as APIs próprias instaladas em cada VM"""
    
    def testar_vm(nome, url_base):
        """Testa uma VM específica com múltiplos endpoints"""
        resultados = {}
        
        # Teste de latência pura
        try:
            start = time.perf_counter()
            response = requests.get(f"{url_base}/ping", timeout=5)
            end = time.perf_counter()
            resultados['latencia_pura_ms'] = round((end - start) * 1000, 2) if response.status_code == 200 else None
        except:
            resultados['latencia_pura_ms'] = None
        
        # Health check
        try:
            start = time.perf_counter()
            response = requests.get(f"{url_base}/health", timeout=5)
            end = time.perf_counter()
            resultados['health_check_ms'] = round((end - start) * 1000, 2) if response.status_code == 200 else None
        except:
            resultados['health_check_ms'] = None
        
        # Estatísticas do servidor
        try:
            response = requests.get(f"{url_base}/stats", timeout=10)
            if response.status_code == 200:
                resultados['stats'] = response.json()
            else:
                resultados['stats'] = None
        except:
            resultados['stats'] = None
        
        # Teste de CPU
        try:
            start = time.perf_counter()
            response = requests.get(f"{url_base}/cpu-test?duration=200", timeout=10)
            end = time.perf_counter()
            if response.status_code == 200:
                cpu_data = response.json()
                cpu_data['total_request_time_ms'] = round((end - start) * 1000, 2)
                resultados['cpu_test'] = cpu_data
            else:
                resultados['cpu_test'] = None
        except:
            resultados['cpu_test'] = None
        
        resultados['servidor'] = nome
        resultados['url_base'] = url_base
        resultados['timestamp'] = datetime.now().isoformat()
        
        return resultados
    
    # Testa todas as VMs em paralelo
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(testar_vm, "MGC", MGC_URL),
            executor.submit(testar_vm, "AWS US", AWS_US_URL),
            executor.submit(testar_vm, "AWS BR", AWS_BR_URL)
        ]
        
        resultados = {}
        for future in futures:
            resultado = future.result()
            nome = resultado['servidor']
            resultados[nome.lower().replace(' ', '_')] = resultado
    
    # Análise comparativa de latência pura
    latencias_puras = {k: v['latencia_pura_ms'] for k, v in resultados.items() if v['latencia_pura_ms'] is not None}
    
    analise = {
        "melhor_latencia": min(latencias_puras.keys(), key=lambda k: latencias_puras[k]) if latencias_puras else None,
        "ranking_latencia": sorted(latencias_puras.items(), key=lambda x: x[1]) if latencias_puras else [],
        "vms_online": len([v for v in resultados.values() if v['latencia_pura_ms'] is not None]),
        "total_vms": len(resultados)
    }
    
    return jsonify({
        "resultados": resultados,
        "analise": analise,
        "metodologia": "Teste usando APIs próprias em cada VM",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/comparacao-detalhada")
def api_comparacao_detalhada():
    """Comparação detalhada incluindo testes de performance"""
    
    def teste_completo_vm(nome, url_base):
        """Executa bateria completa de testes em uma VM"""
        inicio = time.time()
        resultado = {
            'servidor': nome,
            'url_base': url_base,
            'testes': {},
            'disponibilidade': True
        }
        
        # 1. Ping básico
        try:
            start = time.perf_counter()
            response = requests.get(f"{url_base}/ping", timeout=3)
            end = time.perf_counter()
            if response.status_code == 200:
                resultado['testes']['ping'] = {
                    'tempo_ms': round((end - start) * 1000, 2),
                    'status': 'OK'
                }
            else:
                raise Exception(f"Status code: {response.status_code}")
        except Exception as e:
            resultado['testes']['ping'] = {
                'tempo_ms': None,
                'status': 'ERRO',
                'erro': str(e)
            }
            resultado['disponibilidade'] = False
        
        # Se VM não responde ao ping, pula outros testes
        if not resultado['disponibilidade']:
            resultado['tempo_total_s'] = round(time.time() - inicio, 2)
            return resultado
        
        # 2. Estatísticas do sistema
        try:
            response = requests.get(f"{url_base}/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                resultado['testes']['sistema'] = {
                    'cpu_percent': stats['current_stats']['cpu_percent'],
                    'memory_percent': stats['current_stats']['memory_percent'],
                    'disk_percent': stats['current_stats']['disk_percent'],
                    'cpu_count': stats['server_info']['cpu_count'],
                    'memory_total_gb': stats['server_info']['memory_total_gb'],
                    'status': 'OK'
                }
            else:
                raise Exception(f"Status code: {response.status_code}")
        except Exception as e:
            resultado['testes']['sistema'] = {
                'status': 'ERRO',
                'erro': str(e)
            }
        
        # 3. Teste de CPU
        try:
            start = time.perf_counter()
            response = requests.get(f"{url_base}/cpu-test?duration=500", timeout=10)
            end = time.perf_counter()
            if response.status_code == 200:
                cpu_data = response.json()
                resultado['testes']['cpu'] = {
                    'tempo_requisicao_ms': round((end - start) * 1000, 2),
                    'tempo_processamento_ms': cpu_data['actual_processing_time_ms'],
                    'eficiencia': round(cpu_data['actual_processing_time_ms'] / (end - start) / 1000, 2),
                    'status': 'OK'
                }
            else:
                raise Exception(f"Status code: {response.status_code}")
        except Exception as e:
            resultado['testes']['cpu'] = {
                'status': 'ERRO',
                'erro': str(e)
            }
        
        # 4. Teste de conectividade externa
        try:
            start = time.perf_counter()
            response = requests.get(f"{url_base}/network-test", timeout=15)
            end = time.perf_counter()
            if response.status_code == 200:
                network_data = response.json()
                resultado['testes']['conectividade_externa'] = {
                    'tempo_total_ms': round((end - start) * 1000, 2),
                    'sucessos': network_data['successful_requests'],
                    'total_testes': len(network_data['results']),
                    'taxa_sucesso': round(network_data['successful_requests'] / len(network_data['results']) * 100, 1),
                    'detalhes': network_data['results'],
                    'status': 'OK'
                }
            else:
                raise Exception(f"Status code: {response.status_code}")
        except Exception as e:
            resultado['testes']['conectividade_externa'] = {
                'status': 'ERRO',
                'erro': str(e)
            }
        
        resultado['tempo_total_s'] = round(time.time() - inicio, 2)
        return resultado
    
    # Executa testes em paralelo
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(teste_completo_vm, "MGC", MGC_URL),
            executor.submit(teste_completo_vm, "AWS US", AWS_US_URL),
            executor.submit(teste_completo_vm, "AWS BR", AWS_BR_URL)
        ]
        
        resultados = {}
        for future in futures:
            resultado = future.result()
            nome = resultado['servidor']
            resultados[nome.lower().replace(' ', '_')] = resultado
    
    # Análise comparativa
    vms_online = {k: v for k, v in resultados.items() if v['disponibilidade']}
    
    if vms_online:
        # Ranking por latência
        latencias = {k: v['testes']['ping']['tempo_ms'] for k, v in vms_online.items() 
                    if v['testes']['ping']['status'] == 'OK'}
        
        # Ranking por CPU
        cpu_performance = {k: v['testes']['cpu']['eficiencia'] for k, v in vms_online.items() 
                          if v['testes'].get('cpu', {}).get('status') == 'OK'}
        
        analise_comparativa = {
            "ranking_latencia": sorted(latencias.items(), key=lambda x: x[1]) if latencias else [],
            "ranking_cpu": sorted(cpu_performance.items(), key=lambda x: x[1], reverse=True) if cpu_performance else [],
            "vms_online": len(vms_online),
            "total_vms": len(resultados),
            "melhor_latencia": min(latencias.keys(), key=lambda k: latencias[k]) if latencias else None,
            "melhor_cpu": max(cpu_performance.keys(), key=lambda k: cpu_performance[k]) if cpu_performance else None
        }
    else:
        analise_comparativa = {
            "ranking_latencia": [],
            "ranking_cpu": [],
            "vms_online": 0,
            "total_vms": len(resultados),
            "melhor_latencia": None,
            "melhor_cpu": None
        }
    
    return jsonify({
        "resultados": resultados,
        "analise": analise_comparativa,
        "metodologia": {
            "descricao": "Comparação usando APIs próprias em cada VM",
            "testes_executados": ["ping", "sistema", "cpu", "conectividade_externa"],
            "execucao_paralela": True
        },
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    print("🚀 Iniciando servidor na porta 5000")
    print(f"📊 MGC URL: {MGC_URL}")
    print(f"📊 AWS US URL: {AWS_US_URL}")
    print(f"📊 AWS BR URL: {AWS_BR_URL}")
    print("🌐 Acesse: http://localhost:5000")
    print("\n⚠️  LEMBRE-SE: Substitua {SEU_IP_VM_MGC}, {SEU_IP_VM_AWS_US} e {SEU_IP_VM_AWS_BR} pelos IPs reais!")
    app.run(host="0.0.0.0", port=5000, debug=True)
