# Validación de la base compartida

Fecha: 2026-11-08 (America/Santiago). Rama: `feature/tarea6-base-compartida`.
Base: `main` actualizado con `origin/main`, commit
`5c476c6fbc5958b4a8c34f05c4d2ca39b5042dd4`. El repositorio estaba limpio.

| Comprobación | Resultado local |
|---|---|
| Gateway: pytest con warnings como errores | **37 passed** |
| Frontend: instalación limpia `npm ci`, Node 22.23.4 | Correcta, lockfile reproducible |
| Frontend: Vitest / Testing Library | **8 passed** |
| Frontend: `npm run build` (TypeScript + Vite) | Correcto, 97 módulos transformados |
| Dependencias frontend: auditoría de npm durante `npm ci` | 0 vulnerabilidades reportadas |
| Thread Service: suite original sin cambios | **101 passed, 6 skipped** |
| Generador Kubernetes: pruebas exclusivamente offline | **20 passed** |
| `docker compose -f integration/compose.yaml config --quiet` | Correcto |
| Uvicorn/Vite reales en localhost | Correcto: salud y proxy GraphQL |
| Código y manifiestos anteriores contra origin/main | Sin diferencias |
| `git diff --check` | Sin errores |

Total de pruebas: **166 aprobadas, 6 omitidas**. Los tests ASGI se ejecutaron
fuera de las restricciones de sockets del sandbox, en entornos Python separados
para Gateway y Thread Service. No se cambiaron las dependencias originales.

## Alcance comprobado

- Gateway inicia sin URLs externas y también con seis URLs inaccesibles, sin
  solicitudes salientes; devuelve salud y carga la introspección.
- Snapshot SDL independiente compara todos los tipos, campos, argumentos,
  nullabilidad y valores por defecto del contrato v1 (sin depender del orden).
- Las 16 operaciones de dominio pendientes devuelven `NOT_IMPLEMENTED`.
- Transporte compartido probado con MockTransport: códigos HTTP, timeouts,
  fallas de conexión, JSON inválido y conservación de snake_case.
- Errores inesperados ocultan mensaje y extensiones privadas, incluso en debug.
- Todas las pantallas, navegación y enlaces activos funcionan en React Router;
  el scaffold no llama servicios. El cliente compartido usa `/graphql` del
  origen actual y se prueba con fetch controlado.
- Smoke HTTP con procesos Uvicorn y Vite temporales: GET /health, POST /graphql
  directo, consulta health y error de dominio a través de Vite; las cinco rutas
  reciben el HTML SPA al acceder directamente. Los procesos se detuvieron al
  terminar. Los tests de React verifican el contenido de las rutas.
- Revisión de archivos nuevos: solo código, ejemplos seguros de entorno,
  lockfile y documentación; sin .env reales, tokens, builds ni temporales.

## Límites

Las seis omisiones de la suite original requieren MongoDB y/o RabbitMQ de prueba;
no estaban configurados `THREAD_TEST_MONGODB_URL` ni `THREAD_TEST_RABBITMQ_URL`.
No se usaron servicios del clúster como sustituto.

Docker CLI y Compose están disponibles, pero **el daemon Docker no está
funcionando** en este entorno. Se validó Compose, pero no se ejecutaron localmente
`docker build` ni `docker compose up`. El workflow nuevo `tarea6.yml` incluye
build de ambas imágenes para validación en GitHub Actions. Consultar el estado
de esos jobs en el PR; no asumir su aprobación a partir de las pruebas locales.

No se ejecutaron operaciones contra Kubernetes, ni se modificaron manifiestos,
servicios externos o lógica/esquemas/endpoints/pruebas de Thread Service.
La imagen frontend es de desarrollo; hosting de producción y Kubernetes
corresponden a PRs posteriores. El contrato GraphQL v1 se conserva completo,
sin campos adicionales ni funcionalidades de dominio implementadas.

## Comandos principales

Desde raíz, usando entornos separados como indica el contrato:

```sh
/tmp/thread-gateway-venv/bin/python -m pytest -c gateway/pytest.ini gateway/tests -q -W error
/tmp/thread-original-venv/bin/python -m pytest -q -W error
/tmp/thread-original-venv/bin/python -m pytest scripts/test_k8s_rendering.py -q -W error
docker compose -f integration/compose.yaml config --quiet
git diff --check
git diff origin/main -- app tests k8s scripts requirements.txt requirements-dev.txt Dockerfile docker-compose.yaml pytest.ini
```

Desde frontend/, con Node 22:

```sh
npm ci
npm test
npm run build
```

Para reproducir el smoke, iniciar los dos servidores como indica el contrato y
probar `curl --fail http://localhost:5000/health` y POST `{ health }` tanto en
`http://localhost:5000/graphql` como en `http://localhost:5173/graphql`.
