# PlanMinUPN 2026-2 · G05 Santa Elena

Distribución independiente del grupo G05, release académico **DS05/EXP03**. Árbol preparado desde [`Cesar-Bray04/PlanMinUPN-G05`](https://github.com/Cesar-Bray04/PlanMinUPN-G05/commit/f8b92e616cc44f2e9cc8a01ddc8b2752c1668f1d) en el SHA `f8b92e616cc44f2e9cc8a01ddc8b2752c1668f1d`. Este repositorio empieza con un commit propio; no importa el historial del equipo anterior.

## Inicio

1. Clona este repositorio y abre su raíz en PyCharm.
2. Usa Python 3.12. Crea un entorno virtual e instala `python -m pip install -r requirements.txt`.
3. Ejecuta `python -m pytest -q` para comprobar la distribución.
4. Selecciona **Kai Planeamiento** desde `.github/agents/kai-planeamiento.agent.md` en Copilot. Consulta `AGENTS.md` y la guía del grupo.

Los datos fuente están en `data/raw/`. Los derivados M01/M01B conservados pertenecen a este grupo. `.kai_local/` contiene progreso individual local y no debe publicarse.

## Recorrido y productos G05

Abre `index.html` y `docs/learning/TEORIA_KAI_G05.md`. Kai usa `kai/recorrido_g05.py` para E1 → S11 → S12 y genera fichas y entregables individuales dentro de `.kai_local/`. `MISION_S11.cmd`, `MISION_S12.cmd` y `VERIFICAR_PRODUCTOS_G05.cmd` ofrecen las entradas Windows; también puedes ejecutar `python -m src.missions.g05 verificar`.

`outputs/g05_products.json` apunta a las generaciones académicas verificadas S11 `4cc61d4696212e9928cc` y S12 `c1b396f1482e4ee1d39d`. Los modelos y visores se encuentran en `outputs/g05_s11/` y `outputs/g05_s12/`. Los candidatos didácticos no acreditan recursos o reservas profesionales.

La conversación real con Kai en Copilot/PyCharm y la revisión visual interactiva requieren aceptación humana separada.
