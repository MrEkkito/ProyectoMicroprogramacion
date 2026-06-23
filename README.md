# Detector de Velocidad Vehicular con Raspberry Pi 5

![Radar de velocidad](https://content.nationalgeographic.com.es/medio/2023/12/08/radar-de-trafico_923736f6_231208120616_1280x720.jpg)

Sistema de monitoreo de velocidad vehicular desarrollado con Raspberry Pi 5, sensores ultrasónicos HC-SR04, Flask y SQLite. El sistema calcula la velocidad de un vehículo entre dos puntos de medición, registra infracciones, captura evidencia fotográfica mediante IP Webcam y muestra la información en un dashboard web en tiempo real.

---

## Características

- Medición de velocidad mediante dos sensores HC-SR04.
- Dashboard web desarrollado con Flask.
- Almacenamiento local usando SQLite.
- Captura automática de fotografías mediante IP Webcam.
- Activación de sirena mediante buzzer PWM.
- Activación de luces LED USB mediante uhubctl.
- Historial de multas con evidencia fotográfica.
- Actualización en tiempo real mediante AJAX.

---

## Requisitos de Hardware

- Raspberry Pi 5
- 2 Sensores ultrasónicos HC-SR04
- 1 Buzzer activo o pasivo
- Hub USB compatible con uhubctl
- Luces LED USB
- Teléfono Android con IP Webcam
- Fuente de alimentación para Raspberry Pi

---

## Diagrama de Conexiones

| Componente | Raspberry Pi |
|------------|--------------|
| HC-SR04 #1 TRIG | GPIO 23 |
| HC-SR04 #1 ECHO | GPIO 24 |
| HC-SR04 #2 TRIG | GPIO 27 |
| HC-SR04 #2 ECHO | GPIO 22 |
| Buzzer | GPIO 18 |
| Sensores VCC | 5V |
| Sensores GND | GND |

---

## Instalación

### Actualizar el sistema

```bash
sudo apt update
sudo apt upgrade -y
```

### Instalar Python y herramientas necesarias

```bash
sudo apt install python3 python3-pip git sqlite3 -y
```

### Clonar el repositorio

```bash
git clone https://github.com/USUARIO/REPOSITORIO.git
cd REPOSITORIO
```

### Crear entorno virtual

```bash
python3 -m venv venv
```

### Activar entorno virtual

```bash
source venv/bin/activate
```

### Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Dependencias Principales

Instalación manual:

```bash
pip install flask
pip install gpiozero
pip install requests
pip install lgpio
```

---

## Instalación de uhubctl

Necesario para controlar los puertos USB.

```bash
sudo apt install uhubctl -y
```

Verificar dispositivos:

```bash
uhubctl
```

---

## Configuración de la Cámara IP

### Android

Instalar:

- IP Webcam

Iniciar la aplicación y copiar la dirección IP mostrada.

Ejemplo:

```text
http://192.168.1.100:8080
```

Modificar en el código:

```python
IP_CAMARA = "192.168.1.100:8080"
```

---

## Estructura del Proyecto

```text
proyecto/
│
├── app.py
├── radar.db
├── requirements.txt
├── static/
│   └── multas/
├── templates/
└── README.md
```

---

## Ejecución

Activar entorno virtual:

```bash
source venv/bin/activate
```

Ejecutar aplicación:

```bash
python3 app.py
```

---

## Acceso al Dashboard

Desde cualquier dispositivo conectado a la misma red:

```text
http://IP_RASPBERRY:5000
```

Ejemplo:

```text
http://192.168.1.50:5000
```

---

## Funcionamiento

1. El vehículo pasa frente al Sensor 1.
2. Se registra el tiempo inicial.
3. El vehículo pasa frente al Sensor 2.
4. Se registra el tiempo final.
5. Se calcula la velocidad.
6. Se compara con el límite establecido.
7. Si existe infracción:
   - Se activa la sirena.
   - Se encienden las luces LED.
   - Se captura una fotografía.
   - Se registra la multa en SQLite.
8. El dashboard se actualiza automáticamente.

---

## Base de Datos

Tabla principal:

```sql
CREATE TABLE multas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT,
    hora TEXT,
    velocidad REAL,
    tiempo REAL,
    foto TEXT
);
```

---

## Integrantes y Contribuciones

| Integrante | Aporte |
|------------|---------|
| Gerson | Programación de sensores, desarrollo de la base de datos SQLite y gestión del almacenamiento de infracciones. |
| Fabiola | Desarrollo de la interfaz web, diseño del dashboard y actualización de información en tiempo real. |
| Pedro | Integración del hardware, conexión de sensores y actuadores, elaboración de documentación técnica y realización de pruebas del sistema. |

### Distribución de Responsabilidades

- **Gerson**
  - Configuración y programación de los sensores ultrasónicos HC-SR04.
  - Implementación de la lógica de cálculo de velocidad.
  - Diseño e implementación de la base de datos SQLite.
  - Registro y almacenamiento de multas.

- **Fabiola**
  - Desarrollo de la interfaz web utilizando Flask.
  - Diseño del dashboard de monitoreo.
  - Implementación de la visualización del historial de infracciones.
  - Integración de las consultas AJAX para actualización en tiempo real.

- **Pedro**
  - Montaje e integración de los componentes electrónicos.
  - Conexión de la Raspberry Pi con sensores, buzzer y luces LED.
  - Elaboración de diagramas, documentación técnica y manual de instalación.
  - Realización de pruebas funcionales y validación del sistema.

## Licencia

Proyecto académico desarrollado con fines educativos.
