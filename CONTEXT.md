# CAPI kisabella — Contexto del Dominio

## Propósito del sistema
Herramienta interna para evaluar la rentabilidad de ideas de productos físicos antes de comprometer inversión. El sistema toma datos de costos, precios y volumen, y un equipo de agentes de IA analiza si la idea es viable, con qué margen, qué riesgos presenta y qué estrategia comercial seguir.

**Problema que resuelve:** Tomar decisiones de inversión basadas en intuición o en hojas de cálculo manuales propensas a error. CAPI kisabella centraliza, automatiza y enriquece ese análisis con inteligencia de mercado en tiempo real.

---

## Usuarios

| Rol | Descripción |
|-----|-------------|
| Evaluador | Ingresa los datos de la idea y revisa el veredicto |
| Decisor | Usa el historial y las comparativas para priorizar inversiones |

Son 2-3 personas del equipo interno. Mismas personas pueden jugar ambos roles.

---

## Glosario del dominio

| Término | Definición en este sistema |
|---------|---------------------------|
| **Evaluación** | Una idea de producto que pasa por el pipeline completo de análisis |
| **Pipeline** | Secuencia de agentes que analizan una evaluación en paralelo |
| **Veredicto** | Resultado final: `viable`, `viable_con_ajustes` o `no_viable` |
| **Score** | Puntuación 0-100 por agente y score compuesto total |
| **Análisis extenso** | Reporte escrito de 300-500 palabras por agente especialista |
| **Semáforo** | Indicador visual: verde (viable), amarillo (con ajustes), rojo (no viable) |
| **Orquestador** | Agente que consolida los 4 análisis y emite el veredicto final |
| **TC** | Tipo de cambio USD/MXN consultado en tiempo real desde Banxico |
| **Costo total** | Suma de los 11 componentes de costo (ver abajo) |
| **Margen bruto** | (Precio de venta − Costo de compra) / Precio de venta |
| **Margen neto** | (Precio de venta − Costo total) / Precio de venta |
| **ROI** | Retorno sobre inversión inicial en el período evaluado |
| **Punto de equilibrio** | Unidades mínimas para cubrir costos fijos |
| **Comparativa** | Vista lado a lado de 2-3 evaluaciones para decidir cuál priorizar |

---

## Modelo de negocio evaluado

La empresa opera como **importador/distribuidor** y **revendedor** de productos físicos en México. Los proveedores son extranjeros (costos en USD), las ventas son en MXN. No evalúa productos digitales ni SaaS.

**Categorías de producto:** físico (principal) + servicios (secundario).

---

## Estructura de costos

Los 11 componentes de costo que el sistema captura y analiza:

| # | Componente | Tipo |
|---|-----------|------|
| 1 | Costo de compra / precio proveedor | Fijo por unidad (USD → MXN) |
| 2 | Flete internacional | Fijo o por unidad |
| 3 | Aranceles / impuestos de importación | % sobre valor |
| 4 | Almacenamiento / bodega | MXN/mes |
| 5 | Logística — Vehículo | MXN (combustible, desgaste, renta) |
| 6 | Logística — Viáticos | MXN (alimentación, hospedaje) |
| 7 | Logística — Personal | MXN (salario/comisión entrega) |
| 8 | Merma / devoluciones | % sobre unidades |
| 9 | Comisión de vendedor o canal | % sobre precio de venta |
| 10 | Marketing / adquisición de cliente | MXN fijo o por unidad |
| 11 | Overhead fijo prorrateado | MXN (gastos generales asignados) |

---

## Los 5 agentes y sus responsabilidades

### Agente Financiero
Trabaja exclusivamente con los números del formulario.
- Calcula: margen bruto, margen neto, ROI, punto de equilibrio
- Proyecta: flujo de caja a 3 y 6 meses
- Analiza: sensibilidad al tipo de cambio (¿qué pasa si el TC sube/baja 10%?)

### Agente de Mercado
Usa búsqueda web (Tavily) para inteligencia externa.
- Busca: precios actuales de productos similares en competidores
- Estima: demanda del mercado y tendencias
- Benchmarks: márgenes típicos en la industria, canales de distribución

### Agente de Riesgo
Identifica amenazas al negocio.
- Evalúa: dependencia de proveedor único, alternativas disponibles
- Analiza: volatilidad histórica del TC y su impacto en costos
- Revisa: estacionalidad del producto, barreras regulatorias/arancelarias
- Detecta: riesgo de sustitución por alternativas más baratas

### Agente de Estrategia Comercial
Define el camino a la rentabilidad.
- Recomienda: precio de venta con justificación de mercado
- Define: canal óptimo (marketplace / venta directa / distribuidor)
- Calcula: volumen mínimo rentable por canal
- Propone: estrategia de entrada al mercado

### Agente Orquestador
Sintetiza y decide. No tiene score propio.
- Consolida los 4 análisis
- Resuelve contradicciones entre agentes
- Emite el veredicto final con justificación completa
- Calcula el score compuesto ponderado

---

## Flujo de una evaluación

```
1. Usuario llena el formulario (datos de producto, costos, precio, volumen)
2. POST /api/evaluations devuelve 202 + evaluation_id (en <2 segundos)
3. BackgroundTask consulta TC USD/MXN (Banxico con cache 1h, fallback a último valor en DB)
4. Pipeline LangGraph se dispara en background con status=running
5. Agentes 1-4 corren en paralelo (asyncio.gather, ~30-60s total, timeout 90s)
6. Orquestador espera a los 4, sintetiza y emite veredicto final
   - ≥3 agentes OK → veredicto normal
   - 2 OK → viable_con_ajustes + requires_human_review
   - ≤1 OK → no_viable + "Datos insuficientes"
7. Frontend hace polling cada 2s sobre GET /api/evaluations/{id}
8. Status pasa pending → queued → running → complete (o error)
9. Dashboard muestra: semáforo + scorecard + análisis extenso por agente + warn flags
10. Usuario puede re-evaluar (crea evaluación nueva, audit trail inmutable) o hacer chat de seguimiento
```

**Degradación graceful**: si Tavily falla, el agente Mercado procede sin búsqueda web (flag `warn_no_web`). Si Banxico falla, se usa el último TC en DB (flag `warn_fx`).

**Idempotencia**: dos submits idénticos en 30s → 409 Conflict (no se crean evaluaciones duplicadas).

---

## Decisiones de diseño importantes

| Decisión | Elección | Razón | ADR |
|----------|----------|-------|-----|
| LLM | Claude Sonnet 4.6 vía `langchain-anthropic` | Razonamiento financiero sólido. `with_structured_output` valida Pydantic. | ADR-007 |
| Orquestación | LangGraph | Grafos con nodos paralelos y estado compartido. Fan-out → fan-in nativo. | ADR-001 |
| Patrón agente | Funciones puras `AgentFn`, no clases | Composability + testeable con `FakeLLMClient`. Sumar agente = 1 línea registry. | ADR-001 |
| Pipeline | Async vía BackgroundTasks. POST devuelve 202. | Evita timeout Nginx con 4 agentes paralelos. Frontend hace polling. | ADR-006 |
| Búsqueda web | Tavily, llamado directo (NO bind_tools) | Determinístico, cache controlado, prompts más cortos. | ADR-011 |
| TC en tiempo real | Banxico con cache 1h + fallback DB | Fuente oficial. Sin runaway de quota. | — |
| Persistencia de TC | `exchange_rate_used` + `exchange_rate_at` | Análisis histórico reproduce con el TC original, no el actual. | ADR-005 |
| Despliegue | Docker Compose en VPS IONOS ($8-12/mes) | TCO ~$100/año. IP whitelist nativa. Sin vendor lock-in. | ADR-009 |
| Acceso | IP whitelist en Nginx (renderada desde env) | 2-3 users internos. Sin auth compleja. | ADR-010 |
| Base de datos | PostgreSQL 16 + RLS efectivo (FORCE + bindparams) | Defensa-en-profundidad real, no solo declarada. | ADR-008 |
| Tipos compartidos | `openapi-typescript` codegen | Drift backend/frontend imposible. | ADR-004 |
| Idioma | Español end-to-end (UI, prompts, errores) | Equipo y contexto 100% español. | — |

Las ADRs viven en `docs/adr/`. Una ADR nueva por cualquier decisión que afecte 2+ sprints.

---

## Lo que este sistema NO hace (límites de scope)

- No evalúa productos digitales, SaaS ni aplicaciones
- No integra con ERP ni sistemas contables externos (v1)
- No genera contratos ni documentos legales
- No conecta directamente con proveedores o marketplaces
- No tiene módulo de seguimiento post-lanzamiento (roadmap futuro)
- No es accesible públicamente — solo uso interno
