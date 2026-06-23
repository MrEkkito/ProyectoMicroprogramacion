from flask import Flask, jsonify, render_template_string, send_from_directory, request
from gpiozero import DistanceSensor, PWMOutputDevice
import time
import os
import threading
import requests
import sqlite3

app = Flask(__name__)

IP_TELEFONO = "192.168.84.62:8080"
DISTANCIA_SENSORES = 0.50
LIMITE_VELOCIDAD = 0.3
USB_HUBS = ["1", "2", "3", "4"]

CARPETA_FOTOS = "static/multas"
BASE_DATOS = "radar.db"

os.makedirs(CARPETA_FOTOS, exist_ok=True)

def inicializar_db():
    conn = sqlite3.connect(BASE_DATOS)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS multas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            hora TEXT,
            velocidad REAL,
            tiempo REAL,
            foto TEXT
        )
    """)
    conn.commit()
    conn.close()

def guardar_multa_db(fecha, hora, velocidad, tiempo, foto_nombre):
    conn = sqlite3.connect(BASE_DATOS)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO multas (fecha, hora, velocidad, tiempo, foto) VALUES (?, ?, ?, ?, ?)",
        (fecha, hora, velocidad, tiempo, foto_nombre)
    )
    conn.commit()
    conn.close()

def obtener_todas_las_multas():
    conn = sqlite3.connect(BASE_DATOS)
    cursor = conn.cursor()
    cursor.execute("SELECT id, fecha, hora, velocidad, tiempo, foto FROM multas ORDER BY id DESC")
    columnas = [col[0] for col in cursor.description]
    resultados = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    conn.close()
    return resultados

def vaciar_multas_db():
    conn = sqlite3.connect(BASE_DATOS)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM multas")
    conn.commit()
    conn.close()
    
    for archivo in os.listdir(CARPETA_FOTOS):
        ruta_archivo = os.path.join(CARPETA_FOTOS, archivo)
        try:
            if os.path.isfile(ruta_archivo):
                os.remove(ruta_archivo)
        except Exception as e:
            print(f"No se pudo eliminar el archivo {archivo}: {e}")

inicializar_db()

sensor1 = DistanceSensor(echo=24, trigger=23, max_distance=0.2, threshold_distance=0.1, queue_len=1)
sensor2 = DistanceSensor(echo=22, trigger=27, max_distance=0.2, threshold_distance=0.1, queue_len=1)
buzzer = PWMOutputDevice(18)

estado_sistema = {
    "ultima_velocidad": 0.0,
    "tiempo_transcurrido": 0.0,
    "usb_activos": False,
    "sirena_activa": False,
    "ultima_multa_hora": "Ninguna",
    "estado_radar": "Esperando carro...",
    "ip_telefono": IP_TELEFONO
}

t1 = 0 

def capturar_foto_y_guardar(fecha_str, hora_str, velocidad, tiempo):
    global IP_TELEFONO
    url_foto = f"http://{IP_TELEFONO}/shot.jpg"
    print(f"[Cámara] Intentando capturar foto desde {url_foto}...")
    
    timestamp = int(time.time())
    nombre_archivo = f"multa_{timestamp}.jpg"
    ruta_guardado = os.path.join(CARPETA_FOTOS, nombre_archivo)
    
    exito_foto = False
    try:
        respuesta = requests.get(url_foto, timeout=2.0)
        if respuesta.status_code == 200:
            with open(ruta_guardado, 'wb') as f:
                f.write(respuesta.content)
            print(f"[Cámara] Foto guardada físicamente en: {ruta_guardado}")
            exito_foto = True
        else:
            print(f"[Cámara] El teléfono rechazó la petición. Código HTTP: {respuesta.status_code}")
    except Exception as e:
        print(f"[Cámara] Error al conectar con la cámara IP: {e}")

    foto_registro = nombre_archivo if exito_foto else ""
    guardar_multa_db(fecha_str, hora_str, velocidad, tiempo, foto_registro)
    print("[Base de Datos] Registro de multa guardado en SQLite con éxito.")

def sirena_policial():
    estado_sistema["sirena_activa"] = True
    buzzer.value = 0.5
    fin_sirena = time.time() + 10
    
    while time.time() < fin_sirena and estado_sistema["usb_activos"]:
        for freq in range(500, 1000, 15):
            if not estado_sistema["usb_activos"]:
                break
            buzzer.frequency = freq
            time.sleep(0.01)
            
        for freq in range(1000, 500, -15):
            if not estado_sistema["usb_activos"]:
                break
            buzzer.frequency = freq
            time.sleep(0.01)
            
    buzzer.off()
    estado_sistema["sirena_activa"] = False
    print("[Sirena] Sirena silenciada.")

def apagar_sistema_multa():
    estado_sistema["usb_activos"] = False
    for hub in USB_HUBS:
        os.system(f"sudo uhubctl -l {hub} -a off > /dev/null 2>&1")
    buzzer.off()

def temporizador_penalizacion():
    time.sleep(10)
    print("[Radar] Finalizaron los 10 segundos. Apagando periféricos...")
    apagar_sistema_multa()

def activar_multa_general(velocidad, tiempo):
    estado_sistema["usb_activos"] = True
    
    fecha_actual = time.strftime("%d/%m/%Y")
    hora_actual = time.strftime("%H:%M:%S")
    estado_sistema["ultima_multa_hora"] = hora_actual

    for hub in USB_HUBS:
        os.system(f"sudo uhubctl -l {hub} -a on > /dev/null 2>&1")
        
    threading.Thread(target=sirena_policial, daemon=True).start()
    threading.Thread(target=capturar_foto_y_guardar, args=(fecha_actual, hora_actual, velocidad, tiempo), daemon=True).start()
    threading.Thread(target=temporizador_penalizacion, daemon=True).start()

def carro_detectado_s1():
    global t1
    t1 = time.time()
    estado_sistema["estado_radar"] = "¡Vehículo en zona de medición!"
    print("[Sensor 1] ¡Carro detectado! Cronómetro iniciado.")

def carro_detectado_s2():
    global t1
    t2 = time.time()
    
    if t1 == 0:
        return
        
    dt = t2 - t1
    t1 = 0 
    
    if dt > 0.01: 
        velocidad = DISTANCIA_SENSORES / dt
        estado_sistema["ultima_velocidad"] = round(velocidad, 2)
        estado_sistema["tiempo_transcurrido"] = round(dt, 3)
        
        print(f"[Sensor 2] Tiempo: {dt:.3f}s | Velocidad: {velocidad:.2f} m/s")
        
        if velocidad > LIMITE_VELOCIDAD:
            estado_sistema["estado_radar"] = "¡INFRACTOR DETECTADO! PENALIZACIÓN EN CURSO"
            print(f"[Radar] Exceso de velocidad ({velocidad:.2f} m/s) -> Activando multa.")
            activar_multa_general(round(velocidad, 2), round(dt, 3))
        else:
            estado_sistema["estado_radar"] = "Velocidad legal. Esperando vehículo..."
            print("[Radar] Vehículo pasó a velocidad permitida.")

sensor1.when_in_range = carro_detectado_s1
sensor2.when_in_range = carro_detectado_s2

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Radar de Fotomultas Inteligente - Pi 5</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; padding: 20px 10px; color: #333; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        h1 { color: #1a202c; margin: 0 0 5px 0; font-size: 26px; }
        .subtitle { color: #718096; font-size: 14px; margin-bottom: 20px; }
        
        .status-radar { font-size: 16px; font-weight: bold; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #e2e8f0; background-color: #f7fafc; transition: all 0.3s ease; }
        
        .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .metric-card { background: #f8fafc; border: 1px solid #edf2f7; border-radius: 10px; padding: 15px; text-align: center; }
        .metric-title { font-size: 12px; color: #718096; text-transform: uppercase; font-weight: bold; }
        .metric-value { font-size: 28px; font-weight: bold; color: #2b6cb0; margin-top: 5px; }
        
        .indicator-box { display: flex; justify-content: center; gap: 12px; margin-bottom: 25px; flex-wrap: wrap; }
        .tag { padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 12px; border: 1px solid transparent; }
        .active-red { background-color: #fff5f5; color: #c53030; border-color: #feb2b2; animation: flash 0.8s infinite alternate; }
        .inactive-blue { background-color: #ebf8ff; color: #2b6cb0; border-color: #bee3f8; }
        
        .config-section { background-color: #f7fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 15px; margin-bottom: 25px; text-align: left; }
        .config-section h3 { margin: 0 0 10px 0; font-size: 15px; color: #4a5568; }
        .config-row { display: flex; gap: 10px; }
        .config-input { flex-grow: 1; padding: 8px 12px; border: 1px solid #cbd5e0; border-radius: 6px; font-size: 14px; font-family: monospace; }
        .config-btn { background-color: #3182ce; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 14px; }
        .config-btn:hover { background-color: #2b6cb0; }
        
        .history-section { border-top: 2px solid #edf2f7; padding-top: 20px; text-align: left; }
        .history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .history-header h2 { margin: 0; font-size: 18px; color: #2d3748; }
        .clear-btn { background-color: #e53e3e; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: bold; }
        .clear-btn:hover { background-color: #c53030; }
        
        .table-responsive { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }
        th { background-color: #edf2f7; color: #4a5568; padding: 10px; font-weight: bold; }
        td { padding: 10px; border-bottom: 1px solid #edf2f7; vertical-align: middle; }
        tr:hover { background-color: #fcfdfd; }
        
        .thumb-img { width: 60px; height: 45px; object-fit: cover; border-radius: 4px; cursor: pointer; border: 1px solid #cbd5e0; transition: transform 0.2s; }
        .thumb-img:hover { transform: scale(1.1); }
        .no-image { color: #a0aec0; font-style: italic; font-size: 12px; }
        
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.8); align-items: center; justify-content: center; }
        .modal-content { max-width: 90%; max-height: 85%; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
        .modal-close { position: absolute; top: 15px; right: 25px; color: white; font-size: 35px; font-weight: bold; cursor: pointer; }

        @keyframes flash {
            0% { background-color: #fff5f5; box-shadow: 0 0 5px rgba(229,62,62,0.2); }
            100% { background-color: #fed7d7; box-shadow: 0 0 15px rgba(229,62,62,0.6); }
        }
    </style>
    <script>
        setInterval(function() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    let statusBox = document.getElementById('radar-status');
                    statusBox.innerText = data.estado_radar;
                    
                    if (data.estado_radar.includes("INFRACTOR")) {
                        statusBox.style.backgroundColor = "#fff5f5";
                        statusBox.style.borderColor = "#feb2b2";
                        statusBox.style.color = "#c53030";
                    } else {
                        statusBox.style.backgroundColor = "#f7fafc";
                        statusBox.style.borderColor = "#e2e8f0";
                        statusBox.style.color = "#4a5568";
                    }

                    document.getElementById('speed-val').innerText = data.ultima_velocidad + " m/s";
                    document.getElementById('time-val').innerText = data.tiempo_transcurrido + " s";
                    
                    let usbTag = document.getElementById('usb-tag');
                    if (data.usb_activos) {
                        usbTag.innerText = "🚨 PUERTOS USB: ENCENDIDOS";
                        usbTag.className = "tag active-red";
                    } else {
                        usbTag.innerText = "🔌 PUERTOS USB: APAGADOS";
                        usbTag.className = "tag inactive-blue";
                    }
                    
                    let sirenaTag = document.getElementById('sirena-tag');
                    if (data.sirena_activa) {
                        sirenaTag.innerText = "🔊 SIRENA: SONANDO";
                        sirenaTag.className = "tag active-red";
                    } else {
                        sirenaTag.innerText = "🔇 SIRENA: SILENCIADA";
                        sirenaTag.className = "tag inactive-blue";
                    }
                });
        }, 250);

        function actualizarHistorial() {
            fetch('/obtener_historial')
                .then(response => response.json())
                .then(data => {
                    let tbody = document.getElementById('history-tbody');
                    tbody.innerHTML = "";
                    
                    if (data.length === 0) {
                        tbody.innerHTML = "<tr><td colspan='5' style='text-align:center; color:#a0aec0; padding:20px;'>No hay infracciones registradas en la base de datos sqlite.</td></tr>";
                        return;
                    }

                    data.forEach(multa => {
                        let fotoCelda = "";
                        if (multa.foto) {
                            fotoCelda = `<img class="thumb-img" src="/static/multas/${multa.foto}" onclick="abrirModal(this.src)" alt="Foto Multa">`;
                        } else {
                            fotoCelda = "<span class='no-image'>Sin Imagen</span>";
                        }

                        let fila = `
                            <tr>
                                <td><strong>#${multa.id}</strong></td>
                                <td>${multa.fecha} <br><small style="color:#718096;">${multa.hora}</small></td>
                                <td style="color:#e53e3e; font-weight:bold;">${multa.velocidad} m/s</td>
                                <td>${multa.tiempo} s</td>
                                <td>${fotoCelda}</td>
                            </tr>
                        `;
                        tbody.innerHTML += fila;
                    });
                });
        }

        setInterval(actualizarHistorial, 3000);
        window.onload = actualizarHistorial;

        function guardarNuevaIP() {
            let nuevaIp = document.getElementById('ip-input').value;
            fetch('/cambiar_ip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip: nuevaIp })
            })
            .then(response => response.json())
            .then(data => {
                if(data.estatus === "ok") {
                    alert("¡Dirección IP actualizada y guardada con éxito!");
                } else {
                    alert("Error al intentar guardar la IP.");
                }
            });
        }

        function limpiarTodo() {
            if (confirm("¿Estás seguro de que deseas eliminar todas las multas de la base de datos y borrar las imágenes físicas?")) {
                fetch('/limpiar_historial', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        actualizarHistorial();
                    });
            }
        }

        function abrirModal(src) {
            document.getElementById("img-modal").style.display = "flex";
            document.getElementById("modal-img-content").src = src;
        }
        function cerrarModal() {
            document.getElementById("img-modal").style.display = "none";
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>Fotomultas Raspberry Pi 5 🚔</h1>
        <div class="subtitle">Control de Velocidad, Alerta Sonora de Patrulla y Guardado Local en SQLite</div>
        
        <div id="radar-status" class="status-radar">Esperando carro...</div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">Última Velocidad</div>
                <div id="speed-val" class="metric-value">0.0 m/s</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Tiempo de Tránsito</div>
                <div id="time-val" class="metric-value">0.0 s</div>
            </div>
        </div>

        <div class="indicator-box">
            <div id="usb-tag" class="tag inactive-blue">🔌 PUERTOS USB: APAGADOS</div>
            <div id="sirena-tag" class="tag inactive-blue">🔇 SIRENA: SILENCIADA</div>
        </div>

        <div class="config-section">
            <h3>⚙️ Configuración del Servidor de Cámara (IP Webcam)</h3>
            <div class="config-row">
                <input id="ip-input" class="config-input" type="text" value="{{ ip_telefono_actual }}" placeholder="Ej: 192.168.84.62:8080">
                <button class="config-btn" onclick="guardarNuevaIP()">Guardar IP</button>
            </div>
        </div>

        <div class="history-section">
            <div class="history-header">
                <h2>📋 Historial de Infracciones (Guardado en SQLite)</h2>
                <button class="clear-btn" onclick="limpiarTodo()">Limpiar DB</button>
            </div>
            
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Fecha y Hora</th>
                            <th>Velocidad</th>
                            <th>Tiempo</th>
                            <th>Evidencia Foto</th>
                        </tr>
                    </thead>
                    <tbody id="history-tbody">
                        <tr>
                            <td colspan="5" style="text-align:center; color:#a0aec0; padding:20px;">Cargando historial...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="img-modal" class="modal" onclick="cerrarModal()">
        <span class="modal-close" onclick="cerrarModal()">&times;</span>
        <img class="modal-content" id="modal-img-content">
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, ip_telefono_actual=IP_TELEFONO)

@app.route("/status")
def status():
    return jsonify(estado_sistema)

@app.route("/obtener_historial")
def obtener_historial():
    multas = obtener_todas_las_multas()
    return jsonify(multas)

@app.route("/cambiar_ip", methods=["POST"])
def cambiar_ip():
    global IP_TELEFONO
    datos = request.get_json()
    if datos and "ip" in datos:
        IP_TELEFONO = datos["ip"].strip()
        estado_sistema["ip_telefono"] = IP_TELEFONO
        print(f"[Sistema] Dirección IP de la cámara modificada a: {IP_TELEFONO}")
        return jsonify({"estatus": "ok"})
    return jsonify({"estatus": "error"}), 400

@app.route("/limpiar_historial", methods=["POST"])
def limpiar_historial():
    vaciar_multas_db()
    print("[Base de Datos] Historial de multas e imágenes limpiados completamente.")
    return jsonify({"estatus": "ok"})

@app.route('/static/multas/<filename>')
def descargar_foto(filename):
    return send_from_directory(CARPETA_FOTOS, filename)

if __name__ == "__main__":
    print("[Sistema] Asegurando estado inicial de la pista...")
    apagar_sistema_multa() 
    print("[Sistema] Servidor web iniciado en http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
