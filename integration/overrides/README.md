# Ampliaciones locales

B puede añadir overrides Compose aquí para conectar servicios externos. No copiar
repositorios ajenos ni incorporar credenciales. Ejecutar desde la raíz, por ejemplo:
`docker compose -f integration/compose.yaml -f integration/overrides/local.yaml config`.
Los paths relativos de todos los overrides se resuelven respecto de integration/.
