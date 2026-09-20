# webmonitor



Servicio de monitorización de disponibilidad web: comprueba periódicamente un conjunto
de endpoints HTTP de forma concurrente, registra latencia y estado en una serie temporal,
y notifica por webhook cuando un sitio cambia de estado.

**Demo en vivo:** https://web-monitoring-and-asynchronous-kz0x.onrender.com ·
**API interactiva:** https://web-monitoring-and-asynchronous-kz0x.onrender.com/docs

> La demo corre en el plan gratuito de Render. La primera carga puede tardar unos
> segundos si el servicio estaba suspendido. La lectura es pública; crear, modificar
> o borrar sitios requiere una clave de API.

![Captura del panel](webmonitor/docs/panel.png)

---

## Qué hace

- Comprueba N endpoints **concurrentemente** en cada ronda, con cliente HTTP asíncrono
  y pool de conexiones reutilizado.
- Guarda cada comprobación (estado, código HTTP, latencia, error de transporte) como
  serie temporal.
- Detecta **transiciones** de estado, no fallos sueltos: alerta al caer y al recuperarse,
  nunca en cada comprobación fallida.
- Expone métricas agregadas en base de datos: disponibilidad, latencia media y
  percentil 95 sobre una ventana configurable.
- Sirve un panel web propio desde la misma aplicación, sin build ni dependencias de
  frontend.

## Stack

| Capa | Tecnología | Por qué |
|---|---|---|
| API | FastAPI | Validación por type hints y documentación OpenAPI automática |
| ORM | SQLModel sobre SQLAlchemy async | Un modelo sirve de tabla y de esquema |
| Base de datos | PostgreSQL (Neon) | Agregaciones en SQL y funciones de percentil |
| Cliente HTTP | httpx | Async nativo, transporte simulable en tests |
| Tareas periódicas | APScheduler (`AsyncIOScheduler`) | Corre en el event loop de la API, sin broker |
| Tests | pytest, pytest-asyncio | ~30 tests, sin red ni base de datos en la mayoría |
| CI | GitHub Actions | Tests contra PostgreSQL real y linter en cada push |
| Despliegue | Render | Plan gratuito con despliegue continuo desde `main` |

## Arquitectura

```
[APScheduler]  tick cada 15 s
      │
      ▼
[run_checks]   abre sesión de base de datos
      │
      ├─► SELECT sitios activos ──────────────► PostgreSQL
      ├─► filtra por is_due()                   (intervalo propio de cada sitio)
      ├─► check_many() ───────────────────────► httpx + asyncio.gather
      │        └─► CheckResult × N
      ├─► por cada resultado:
      │        ├─ INSERT HealthLog             (el dato bruto, siempre)
      │        └─ apply_result()               (muta el estado, devuelve transición)
      ├─► COMMIT ─────────────────────────────► PostgreSQL
      └─► cierra sesión
              │
              ▼
      [send_alert] solo si hubo transición ───► webhook
```

La separación por responsabilidades es lo que hace el sistema testeable:

| Módulo | Red | Base de datos | Lógica de negocio |
|---|---|---|---|
| `services/checker.py` | sí | no | no |
| `services/notifier.py` | sí | no | no |
| `services/monitor.py` | no | sí | orquestación |
| `apply_result()` | no | no | sí |

La máquina de estados es una función pura sobre un objeto en memoria, así que toda la
lógica de alertas se prueba sin levantar nada.

## Decisiones de diseño

**APScheduler en lugar de Celery.** Celery necesita un broker y un segundo proceso, que
el plan gratuito no ofrece. `AsyncIOScheduler` ejecuta las corrutinas en el event loop
que FastAPI ya tiene. La contrapartida es que el scheduler vive en memoria del proceso:
con varias réplicas habría comprobaciones duplicadas. Se resolvería con un jobstore
compartido o un lock distribuido, que es el punto donde Celery empieza a compensar.

**Un tick global con filtro, no un job por sitio.** Un job por sitio obligaría a añadir,
quitar y reprogramar jobs en cada alta o baja, manteniendo sincronizados el scheduler y
la base de datos. Con un pulso fijo y `is_due()`, la base de datos es la única fuente de
verdad. El precio es la granularidad: el intervalo configurado es un mínimo, no una
garantía exacta.

**Estado desnormalizado en `MonitoredSite`.** Los campos `status` y
`consecutive_failures` son derivables del histórico, pero se guardan en la fila del sitio
por dos motivos. El coste: contar fallos consecutivos desde el histórico es un escaneo
sin límite superior. Y, sobre todo, porque **alertar depende del estado anterior**: sin
esa memoria no se distingue "está caído" de "acaba de caerse".

**Latencia nula en los fallos.** Un timeout registra `response_time_ms = NULL` en lugar
del valor del timeout. Como `AVG` ignora los nulos, la latencia media refleja solo las
peticiones que realmente respondieron. Disponibilidad y latencia son métricas distintas
y no deben contaminarse.

**Agregación en SQL, no en Python.** Un sitio comprobado cada minuto genera ~43.000 filas
al mes. Las métricas se calculan con `COUNT`, `AVG` y `percentile_cont` apoyadas en un
índice compuesto `(site_id, checked_at)`, sin transferir filas fuera de la base de datos.

**Percentil 95 además de la media.** La media esconde los picos: 95 peticiones de 50 ms y
5 de 3 s dan una media de 197 ms que parece razonable, mientras el p95 revela que uno de
cada veinte usuarios espera 3 segundos.

**Commit antes de notificar.** Alertar dentro de la transacción mantendría filas
bloqueadas durante la llamada al servicio externo, y un fallo posterior del commit
avisaría de una caída que no quedó registrada. Primero los datos, luego el mundo exterior.

**Esquemas de API separados de los modelos de tabla.** Evita *overposting* (un cliente no
puede enviar `status` y falsear la monitorización), permite validaciones distintas según
la dirección, y desacopla el contrato público del esquema interno.

**Fechas en UTC con zona explícita.** El almacenamiento es siempre UTC; la conversión a
hora local ocurre solo en el navegador.

## Ejecutar en local

Requisitos: Python 3.12 o superior.

```bash
git clone https://github.com/gonfdezz/Web-monitoring-and-asynchronous-notifications-API.git

cd webmonitor

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

python3 -m pip install -r requirements-dev.txt
```

Crea un archivo `.env` en la raíz:

```env
# SQLite para desarrollo, o una cadena de PostgreSQL
DATABASE_URL=sqlite+aiosqlite:///./webmonitor.db

FAILURE_THRESHOLD=3
REQUEST_TIMEOUT=10.0

# Opcionales
DISCORD_WEBHOOK_URL=
API_KEY=
```

```bash
uvicorn app.main:app --reload
```

- Panel: http://127.0.0.1:8000
- Documentación de la API: http://127.0.0.1:8000/docs

Las tablas se crean solas al arrancar. Sin `API_KEY` definida, la escritura queda abierta
para facilitar el desarrollo.

> Con SQLite, el endpoint de métricas no funciona: `percentile_cont` es exclusiva de
> PostgreSQL. El resto de la aplicación es idéntica en ambos motores.

## Tests

```bash
python3 -m pytest
python3 -m pytest --cov=app --cov-report=term-missing
```

Por defecto corren contra SQLite en memoria, en menos de un segundo. Para ejecutarlos
contra PostgreSQL, incluidos los tests marcados como exclusivos:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host/db python3 -m pytest
```

Los tests de red usan `httpx.MockTransport`, así que no dependen de conectividad ni de
que un sitio externo esté disponible. Cada caso de fallo (timeout, DNS, 500) se simula de
forma determinista.

GitHub Actions ejecuta la suite completa en cada push, levantando un contenedor de
PostgreSQL 16 como servicio del job.

## Configuración

| Variable | Por defecto | Descripción |
|---|---|---|
| `DATABASE_URL` | SQLite local | Cadena de conexión async (`+aiosqlite` o `+asyncpg`) |
| `FAILURE_THRESHOLD` | `3` | Fallos consecutivos antes de marcar un sitio como caído |
| `REQUEST_TIMEOUT` | `10.0` | Segundos de espera máxima por comprobación |
| `DEFAULT_CHECK_INTERVAL` | `60` | Intervalo por defecto de un sitio nuevo, en segundos |
| `DISCORD_WEBHOOK_URL` | vacío | Destino de las alertas; sin él solo se registran en el log |
| `API_KEY` | vacío | Clave para escritura; sin ella la escritura queda abierta |

## API

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/health` | no | Comprobación de vida del servicio |
| `GET` | `/sites` | no | Lista paginada de sitios vigilados |
| `POST` | `/sites` | sí | Alta de un sitio |
| `GET` | `/sites/{id}` | no | Detalle de un sitio |
| `PATCH` | `/sites/{id}` | sí | Actualización parcial |
| `DELETE` | `/sites/{id}` | sí | Baja, con borrado en cascada del histórico |
| `GET` | `/sites/{id}/logs` | no | Comprobaciones recientes |
| `GET` | `/sites/{id}/metrics` | no | Disponibilidad, latencia media y p95 |

La autenticación es una clave en la cabecera `X-API-Key`.

```bash
curl -X POST https://TU-SERVICIO.onrender.com/sites \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "Python", "url": "https://python.org", "check_interval": 60}'
```

## Limitaciones conocidas

Son decisiones conscientes ligadas al alcance del proyecto y a un despliegue de coste cero:

- **El servicio se suspende tras 15 minutos sin tráfico** en el plan gratuito de Render, y
  con él se detiene el scheduler. Se mantiene activo con un ping externo cada 10 minutos.
  En producción se resolvería con un plan de proceso persistente o separando el scheduler
  de la API.
- **Sin migraciones.** El esquema se crea con `create_all`, que no sabe modificar columnas
  existentes. Alembic es el siguiente paso.
- **`HealthLog` crece sin límite.** Falta una política de retención o agregación por
  ventanas.
- **El scheduler no escala horizontalmente.** Varias réplicas provocarían comprobaciones y
  alertas duplicadas.
- **Autenticación por clave única**, sin usuarios, permisos ni rotación. Suficiente para
  proteger la escritura de una demo pública, insuficiente para multiusuario.
- **La sesión de base de datos permanece abierta durante las peticiones HTTP** de la ronda,
  ocupando una conexión del pool mientras se espera a la red.

## Próximos pasos

- [ ] Migraciones con Alembic
- [ ] Retención del histórico y agregados por hora
- [ ] Notificaciones por correo además de webhook
- [ ] Acortar la ventana de sesión de base de datos en `run_checks`
- [ ] Rate limiting en los endpoints de escritura

## Licencia

MIT
