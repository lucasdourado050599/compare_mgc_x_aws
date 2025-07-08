#!/usr/bin/env python3
"""
API simples para subir em cada VM (MGC e AWS)
Esta API deve ser executada em cada servidor para fazer uma comparação justa
"""

from flask import Flask, jsonify, request
import time
import psutil
import platform
import os
from datetime import datetime
import socket
import requests

app = Flask(__name__)

def get_server_info():
    """Coleta informações do servidor"""
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "disk_total_gb": round(psutil.disk_usage('/').total / (1024**3), 2) if os.name != 'nt' else round(psutil.disk_usage('C:').total / (1024**3), 2)
    }

def get_server_stats():
    """Coleta estatísticas em tempo real do servidor"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent,
        "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None,
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
    }

@app.route("/")
def home():
    """Endpoint raiz com informações básicas"""
    return jsonify({
        "message": "API de Teste de Performance - VM",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "server_info": get_server_info()
    })

@app.route("/health")
def health():
    """Health check simples"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": time.time() - psutil.boot_time()
    })

@app.route("/ping")
def ping():
    """Endpoint ultra-rápido para testar latência pura"""
    return jsonify({
        "pong": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/stats")
def stats():
    """Estatísticas detalhadas do servidor"""
    return jsonify({
        "server_info": get_server_info(),
        "current_stats": get_server_stats(),
        "timestamp": datetime.now().isoformat()
    })

@app.route("/cpu-test")
def cpu_test():
    """Teste que consome CPU para simular carga"""
    start_time = time.time()
    
    # Operação que consome CPU por alguns milissegundos
    duration = request.args.get('duration', 100, type=int)  # ms
    duration = min(duration, 5000)  # Máximo 5 segundos
    
    end_time = start_time + (duration / 1000)
    while time.time() < end_time:
        _ = sum(i*i for i in range(1000))
    
    processing_time = (time.time() - start_time) * 1000
    
    return jsonify({
        "test": "cpu-intensive",
        "requested_duration_ms": duration,
        "actual_processing_time_ms": round(processing_time, 2),
        "cpu_percent_during": psutil.cpu_percent(),
        "timestamp": datetime.now().isoformat()
    })

@app.route("/memory-test")
def memory_test():
    """Teste que consome memória"""
    start_time = time.time()
    
    # Aloca uma quantidade de memória
    size_mb = request.args.get('size', 10, type=int)  # MB
    size_mb = min(size_mb, 100)  # Máximo 100MB
    
    try:
        # Cria uma lista que ocupa aproximadamente size_mb MB
        data = [0] * (size_mb * 1024 * 128)  # Aproximadamente size_mb MB
        
        # Acessa os dados para garantir que foram alocados
        checksum = sum(data[::1000])
        
        processing_time = (time.time() - start_time) * 1000
        memory_usage = psutil.virtual_memory().percent
        
        # Libera a memória
        del data
        
        return jsonify({
            "test": "memory-intensive",
            "allocated_mb": size_mb,
            "processing_time_ms": round(processing_time, 2),
            "memory_percent_peak": memory_usage,
            "checksum": checksum,
            "timestamp": datetime.now().isoformat()
        })
    
    except MemoryError:
        return jsonify({
            "error": "Não foi possível alocar a memória solicitada",
            "requested_mb": size_mb
        }), 500

@app.route("/io-test")
def io_test():
    """Teste de I/O de disco"""
    start_time = time.time()
    
    try:
        # Cria um arquivo temporário e escreve dados
        filename = f"/tmp/test_io_{int(time.time())}.tmp"
        if os.name == 'nt':  # Windows
            filename = f"C:\\temp\\test_io_{int(time.time())}.tmp"
            os.makedirs("C:\\temp", exist_ok=True)
        
        size_kb = request.args.get('size', 100, type=int)  # KB
        size_kb = min(size_kb, 1024)  # Máximo 1MB
        
        data = "x" * (size_kb * 1024)
        
        # Escreve o arquivo
        write_start = time.time()
        with open(filename, 'w') as f:
            f.write(data)
        write_time = (time.time() - write_start) * 1000
        
        # Lê o arquivo
        read_start = time.time()
        with open(filename, 'r') as f:
            read_data = f.read()
        read_time = (time.time() - read_start) * 1000
        
        # Remove o arquivo
        os.remove(filename)
        
        total_time = (time.time() - start_time) * 1000
        
        return jsonify({
            "test": "io-intensive",
            "file_size_kb": size_kb,
            "write_time_ms": round(write_time, 2),
            "read_time_ms": round(read_time, 2),
            "total_time_ms": round(total_time, 2),
            "data_integrity": len(read_data) == len(data),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            "error": f"Erro no teste de I/O: {str(e)}"
        }), 500

@app.route("/network-test")
def network_test():
    """Teste de conectividade de rede"""
    start_time = time.time()
    
    test_urls = [
        "https://www.google.com",
        "https://httpbin.org/get",
        "https://viacep.com.br/ws/01001000/json/"
    ]
    
    results = []
    
    for url in test_urls:
        try:
            url_start = time.time()
            response = requests.get(url, timeout=5)
            url_time = (time.time() - url_start) * 1000
            
            results.append({
                "url": url,
                "status_code": response.status_code,
                "response_time_ms": round(url_time, 2),
                "success": response.status_code == 200
            })
        except Exception as e:
            results.append({
                "url": url,
                "error": str(e),
                "response_time_ms": None,
                "success": False
            })
    
    total_time = (time.time() - start_time) * 1000
    
    return jsonify({
        "test": "network-connectivity",
        "results": results,
        "total_time_ms": round(total_time, 2),
        "successful_requests": sum(1 for r in results if r["success"]),
        "timestamp": datetime.now().isoformat()
    })

@app.route("/benchmark")
def benchmark():
    """Benchmark completo do servidor"""
    start_time = time.time()
    
    # Coleta informações iniciais
    initial_stats = get_server_stats()
    
    # Executa microbenchmarks
    cpu_result = requests.get(f"http://localhost:{request.environ.get('SERVER_PORT', 5000)}/cpu-test?duration=500").json()
    memory_result = requests.get(f"http://localhost:{request.environ.get('SERVER_PORT', 5000)}/memory-test?size=50").json()
    
    # Coleta estatísticas finais
    final_stats = get_server_stats()
    
    total_time = (time.time() - start_time) * 1000
    
    return jsonify({
        "benchmark": "complete",
        "server_info": get_server_info(),
        "initial_stats": initial_stats,
        "final_stats": final_stats,
        "cpu_test": cpu_result,
        "memory_test": memory_result,
        "total_benchmark_time_ms": round(total_time, 2),
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    print("🚀 Iniciando API de Teste de Performance")
    print(f"📊 Servidor: {socket.gethostname()}")
    print(f"💻 Plataforma: {platform.platform()}")
    print(f"🧠 CPU: {psutil.cpu_count()} cores")
    print(f"💾 RAM: {round(psutil.virtual_memory().total / (1024**3), 2)} GB")
    print("🌐 Endpoints disponíveis:")
    print("   GET / - Informações básicas")
    print("   GET /health - Health check")
    print("   GET /ping - Latência mínima")
    print("   GET /stats - Estatísticas do servidor")
    print("   GET /cpu-test?duration=100 - Teste de CPU")
    print("   GET /memory-test?size=10 - Teste de memória")
    print("   GET /io-test?size=100 - Teste de I/O")
    print("   GET /network-test - Teste de rede")
    print("   GET /benchmark - Benchmark completo")
    print("\n🔧 Para usar em produção, configure um servidor WSGI como Gunicorn")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
