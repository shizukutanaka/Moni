# Monitor del Sistema Moni

Moni proporciona monitoreo del sistema con controles de seguridad integrales para uso personal y organizacional.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Licencia: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Seguridad: Reforzada](https://img.shields.io/badge/security-hardened-green.svg)](SECURITY.md)

[Versión en Inglés](README.md) | [Versión en Japonés](README_JP.md) | [Política de Seguridad](SECURITY.md)

---

## Resumen

Moni es una solución de monitoreo del sistema reforzada diseñada para entornos donde la seguridad, estabilidad y rendimiento son críticos. Construida con principios de defensa en profundidad, proporciona métricas en tiempo real sin comprometer la integridad del sistema.

### Capacidades Principales

- **Monitoreo en Tiempo Real** - CPU, memoria, GPU, red, E/S de disco, temperaturas
- **Controles de Seguridad** - Encriptación AES-256-GCM, validación de entrada, limitación de tasa, registro de auditoría
- **Validación Estricta** - Todas las entradas verificadas, operaciones en sandbox, comunicaciones encriptadas
- **Acceso Basado en Roles** - RBAC, 2FA TOTP, logs firmados con HMAC, marcos de cumplimiento (ISO 27001, NIST CSF)
- **Eficiencia de Recursos** - Huella mínima, caché inteligente, estructuras de datos eficientes
- **Recuperación de Fallos** - Recuperación de errores, degradación elegante, failover controlado

---

## Requisitos del Sistema

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| **OS** | Windows 10 / macOS 12 / Ubuntu 20.04 | Windows 11 / macOS 14 / Ubuntu 22.04 |
| **CPU** | 2 núcleos @ 2.0 GHz | 4+ núcleos @ 2.5 GHz |
| **RAM** | 4 GB | 8+ GB |
| **Almacenamiento** | 1 GB libre (SSD preferido) | 5+ GB libre (NVMe SSD) |
| **Python** | 3.10+ | 3.12 |
| **Red** | No requerida | Opcional (para diagnósticos) |

### Componentes Opcionales

- **Monitoreo de GPU**: GPU NVIDIA con controladores NVML (CUDA 11.0+)
- **Métricas Avanzadas**: Unidades con SMART, sensores de temperatura
- **Diagnósticos de Red**: ICMP sin restricciones para pruebas de ping

---

## Inicio Rápido

### Instalación

```bash
# Clonar repositorio
git clone <repository-url>
cd moni

# Crear entorno aislado
python3 -m venv venv

# Activar entorno
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Instalar Moni
pip install -e .

# Verificar instalación
moni --version
```

### Primera Ejecución

```bash
# Lanzar con configuraciones predeterminadas
moni

# Lanzar con refuerzo de seguridad
moni --secure

# Lanzar con perfil específico
moni --profile gaming

# Validar configuración
moni --validate-config

# Ejecutar auditoría de seguridad
moni --security-audit
```

- **Linux/macOS**: `~/.config/moni/`
- **Windows**: `%APPDATA%\moni\`

---

## Uso

### Interfaz de Línea de Comandos

```bash
# Operaciones Principales
moni                                    # Iniciar monitoreo
moni --mode daemon                      # Ejecutar como servicio en segundo plano
moni --mode export                      # Exportar métricas a archivo
moni --validate-config                  # Validar configuración
moni --security-audit                   # Ejecutar evaluación de seguridad

# Gestión de Perfiles
moni --profile gaming                   # Perfil de juegos (actualización 500ms)
moni --profile development              # Perfil de desarrollo
moni --profile minimal                  # Uso mínimo de recursos

# Operaciones de Exportación
moni --mode export --export-format json --export-file report.json
moni --mode export --export-format csv --export-file data.csv
moni --mode export --export-format html --export-file dashboard.html

# Opciones de Seguridad
moni --secure                           # Habilitar todas las características de seguridad
moni --disable-alerts                   # Suprimir notificaciones de alertas
moni --log-level debug                  # Registro detallado

# Avanzado
moni --reset-config                     # Restablecer a predeterminados
moni --config-path /custom/path.json    # Ubicación de configuración personalizada
```

### Perfiles de Configuración

**Perfil de Juegos** - Optimizado para monitoreo de rendimiento en tiempo real
```bash
moni --profile gaming
```
- Actualización: 500ms (2 FPS)
- Métricas: CPU, GPU, memoria, temperaturas
- Alertas: Minimizadas durante pantalla completa

**Perfil de Desarrollo** - Métricas integrales para desarrolladores
```bash
moni --profile development
```
- Actualización: 2000ms
- Métricas: Todas disponibles
- Registro: Habilitado con intervalos de 5s

**Perfil Mínimo** - Solo métricas esenciales
```bash
moni --profile minimal
```
- Actualización: 3000ms
- Métricas: CPU, memoria, tiempo de actividad
- Uso de recursos: <50MB RAM, <1% CPU

---

## Seguridad

### Arquitectura de Seguridad

- **Encriptación en Reposo**: AES-256-GCM para todos los datos de configuración
- **Validación de Entrada**: Sanitización integral en todas las entradas de usuario
- **Protección contra Traverso de Ruta**: Operaciones de archivo en sandbox
- **Prevención de Inyección de Comandos**: Ejecución de subprocesos validada
- **Limitación de Tasa**: Protección DoS integrada
- **Registro de Auditoría**: Logs a prueba de manipulación firmados con HMAC
- **2FA TOTP**: Autenticación multifactor opcional
- **RBAC**: Control de acceso basado en roles para implementaciones empresariales

### Cumplimiento

- **ISO 27001**: Gestión de seguridad de la información
- **Marco de Ciberseguridad NIST**: Implementación de controles de seguridad
- **GDPR**: Principios de protección y privacidad de datos
- **FIPS 140-2**: Estándares de módulo criptográfico

---

## Métricas de Monitoreo

### Métricas del Sistema

| Categoría | Métricas | Frecuencia de Actualización |
|-----------|----------|----------------------------|
| **CPU** | Uso general %, por núcleo %, promedio de carga, frecuencia, temperatura | Tiempo real |
| **Memoria** | Uso de RAM, uso de swap, disponible, actividad de paginación | Tiempo real |
| **GPU** | Utilización %, uso de memoria, temperatura, velocidad del ventilador, potencia | Tiempo real |
| **Disco** | Velocidades de lectura/escritura, utilización %, salud SMART | 5 segundos |
| **Red** | Velocidades de subida/bajada, conexiones, estado de interfaz | Tiempo real |
| **Sistema** | Tiempo de actividad, estado de batería, temperaturas, velocidades de ventiladores | 10 segundos |

### Configuración de Alertas

Las alertas se activan cuando las métricas exceden umbrales configurables:

```json
{
  "automation": {
    "alerts": {
      "enabled": true,
      "cooldown_seconds": 60,
      "thresholds": {
        "cpu_percent": 85.0,
        "memory_percent": 90.0,
        "gpu_temperature_celsius": 83.0,
        "disk_usage_percent": 95.0
      }
    }
  }
}
```

---

## Licencia

Licencia MIT - Ver [LICENSE](LICENSE) para detalles.

Este software se proporciona "tal cual" sin garantía. Úsalo bajo tu propio riesgo, especialmente en entornos críticos.
