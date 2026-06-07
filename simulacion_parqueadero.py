# -*- coding: utf-8 -*-
"""
Simulacion cajeros de parqueadero - Supercentro
Modelo: 1 punto de salida con 3 cajeros independientes M/M/1 (filas independientes,
sin cambio de fila ni desercion). Tiempo de servicio exponencial segun tipo de usuario.

Tipos de usuario:
    Tipo        Servicio(exp media)   Llegada(media)   %
    Rapido            1 min                3 min        25
    Normal            3 min                3 min        20
    Lento             4 min                5 min        30
    Muy lento         6 min                7 min        25
"""
import os
import numpy as np
import simpy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IMG_DIR = "image"   # carpeta de salida de las figuras

# ----------------------------------------------------------------------------
# Parametros del modelo
# ----------------------------------------------------------------------------
TIPOS      = ["Rapido", "Normal", "Lento", "Muy lento"]
SERV_MEAN  = np.array([1.0, 3.0, 4.0, 6.0])   # media exponencial de servicio (min)
LLEG_MEAN  = np.array([3.0, 3.0, 5.0, 7.0])   # media de llegada (min)
PROB       = np.array([0.25, 0.20, 0.30, 0.25])
N_CAJEROS  = 3
HORIZON    = 6000.0     # minutos por replica
N_REPLICAS = 30         # replicas (se valida con la tecnica de la media)
WARMUP_DEFAULT = 0      # se recalcula con Welch

# ----------------------------------------------------------------------------
# Una replica de la simulacion
# ----------------------------------------------------------------------------
def run_replica(seed, horizon=HORIZON):
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    cajeros = [simpy.Resource(env, capacity=1) for _ in range(N_CAJEROS)]

    registros = []  # dict por cliente

    def cliente(env, tipo, caja):
        t_lleg = env.now
        with cajeros[caja].request() as req:
            yield req
            espera = env.now - t_lleg
            serv = rng.exponential(SERV_MEAN[tipo])
            yield env.timeout(serv)
            registros.append(dict(orden=0, tipo=tipo, caja=caja,
                                  llegada=t_lleg, espera=espera,
                                  servicio=serv, sistema=espera + serv))

    def generador(env):
        while True:
            tipo = rng.choice(4, p=PROB)
            ia = rng.exponential(LLEG_MEAN[tipo])
            yield env.timeout(ia)
            caja = int(rng.integers(N_CAJEROS))
            env.process(cliente(env, tipo, caja))

    env.process(generador(env))
    env.run(until=horizon)

    # ordenar por llegada y numerar
    registros.sort(key=lambda r: r["llegada"])
    for i, r in enumerate(registros):
        r["orden"] = i
    return registros


# ----------------------------------------------------------------------------
# 1) Estado estable: tecnica de la media movil (Welch) sobre variable W=tiempo en sistema
# ----------------------------------------------------------------------------
def deteccion_estado_estable(replicas):
    # alinear W por indice de cliente entre replicas
    min_n = min(len(r) for r in replicas)
    W = np.array([[r[i]["sistema"] for i in range(min_n)] for r in replicas])
    W_bar = W.mean(axis=0)                       # promedio entre replicas por cliente
    # media movil (ventana w)
    w = 25
    suav = np.convolve(W_bar, np.ones(2 * w + 1) / (2 * w + 1), mode="valid")
    x_suav = np.arange(w, w + len(suav))
    return W_bar, suav, x_suav, min_n


def detectar_warmup(suav, x_suav):
    # punto donde la media movil entra en banda +-5% de su valor final estable
    final = suav[int(len(suav) * 0.6):].mean()
    banda = 0.05 * final
    dentro = np.abs(suav - final) <= banda
    idx = 0
    for i in range(len(dentro)):
        if dentro[i:].all():
            idx = i
            break
    return int(x_suav[idx]), final


# ----------------------------------------------------------------------------
# 2) Numero de replicas: media acumulada del gran promedio de W vs # replicas
# ----------------------------------------------------------------------------
def estabilidad_replicas(replicas, warmup):
    medias = []
    for r in replicas:
        vals = [c["sistema"] for c in r if c["orden"] >= warmup]
        medias.append(np.mean(vals))
    medias = np.array(medias)
    acum = np.cumsum(medias) / np.arange(1, len(medias) + 1)
    # intervalo de confianza 95% por # de replicas
    n = np.arange(1, len(medias) + 1)
    s = np.array([medias[:i + 1].std(ddof=1) if i > 0 else 0 for i in range(len(medias))])
    hw = 1.96 * s / np.sqrt(n)
    return medias, acum, hw


# ----------------------------------------------------------------------------
# Estadisticas finales (post warmup) por cajero y por tipo
# ----------------------------------------------------------------------------
def estadisticas(replicas, warmup):
    serv_caja = {c: [] for c in range(N_CAJEROS)}
    sis_caja  = {c: [] for c in range(N_CAJEROS)}
    esp_caja  = {c: [] for c in range(N_CAJEROS)}
    cont_tipo_caja = np.zeros((N_CAJEROS, 4))
    serv_tipo = {t: [] for t in range(4)}
    for r in replicas:
        for c in r:
            if c["orden"] < warmup:
                continue
            serv_caja[c["caja"]].append(c["servicio"])
            sis_caja[c["caja"]].append(c["sistema"])
            esp_caja[c["caja"]].append(c["espera"])
            cont_tipo_caja[c["caja"], c["tipo"]] += 1
            serv_tipo[c["tipo"]].append(c["servicio"])
    cont_tipo_caja /= len(replicas)   # promedio por replica
    res = dict(
        serv_caja_mean=[np.mean(serv_caja[c]) for c in range(N_CAJEROS)],
        sis_caja_mean=[np.mean(sis_caja[c]) for c in range(N_CAJEROS)],
        esp_caja_mean=[np.mean(esp_caja[c]) for c in range(N_CAJEROS)],
        cont_tipo_caja=cont_tipo_caja,
        serv_tipo_mean=[np.mean(serv_tipo[t]) for t in range(4)],
        prop_tipo=np.array([len(serv_tipo[t]) for t in range(4)], float),
    )
    res["prop_tipo"] /= res["prop_tipo"].sum()
    return res


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    print("Corriendo", N_REPLICAS, "replicas...")
    replicas = [run_replica(seed=1000 + k) for k in range(N_REPLICAS)]
    print("Clientes promedio por replica:", np.mean([len(r) for r in replicas]))

    # --- estado estable / warmup ---
    W_bar, suav, x_suav, min_n = deteccion_estado_estable(replicas)
    warmup, w_final = detectar_warmup(suav, x_suav)
    print("Warmup (clientes a descartar):", warmup, " W estable ~", round(w_final, 3))

    # --- estabilidad por numero de replicas ---
    medias, acum, hw = estabilidad_replicas(replicas, warmup)

    # --- estadisticas con y sin warmup ---
    est_con = estadisticas(replicas, 0)
    est_sin = estadisticas(replicas, warmup)

    # =========================== FIGURAS ===========================
    # Fig 1: deteccion de estado estable (Welch)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(W_bar, color="#9ecae1", alpha=0.4, label="Promedio entre replicas (crudo)")
    ax.plot(x_suav, suav, color="#08519c", lw=2, label="Media movil (Welch, w=25)")
    ax.axhline(w_final, color="green", ls="--", label=f"Nivel estable ~ {w_final:.2f} min")
    ax.axvline(warmup, color="red", ls=":", lw=2, label=f"Fin transitorio = {warmup} clientes")
    ax.set_xlabel("N de cliente (orden de llegada)")
    ax.set_ylabel("W = tiempo en sistema (min)")
    ax.set_title("Fig 1. Deteccion del estado estable - tecnica de la media (Welch)")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "fig1_estado_estable.png"), dpi=120); plt.close(fig)

    # Fig 2: numero de replicas (media acumulada + IC)
    fig, ax = plt.subplots(figsize=(9, 5))
    n = np.arange(1, len(medias) + 1)
    ax.plot(n, acum, "o-", color="#08519c", label="Media acumulada de W")
    ax.fill_between(n, acum - hw, acum + hw, alpha=0.2, color="#08519c", label="IC 95%")
    ax.set_xlabel("Numero de replicas")
    ax.set_ylabel("W promedio (min)")
    ax.set_title("Fig 2. Estabilizacion del promedio segun numero de replicas")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "fig2_num_replicas.png"), dpi=120); plt.close(fig)

    # Fig 3: tiempo promedio de atencion por cajero (min/max)
    fig, ax = plt.subplots(figsize=(8, 5))
    cajas = [f"Cajero {c+1}" for c in range(N_CAJEROS)]
    vals = est_sin["serv_caja_mean"]
    colors = ["#9ecae1"] * N_CAJEROS
    cmin, cmax = int(np.argmin(vals)), int(np.argmax(vals))
    colors[cmin] = "#31a354"; colors[cmax] = "#de2d26"
    bars = ax.bar(cajas, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom")
    ax.set_ylabel("Tiempo promedio de atencion (min)")
    ax.set_title("Fig 3. Tiempo promedio de atencion por cajero\n(verde=menor, rojo=mayor)")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "fig3_atencion_cajero.png"), dpi=120); plt.close(fig)

    # Fig 4: promedio de usuarios por tipo (total y por cajero)
    fig, ax = plt.subplots(figsize=(9, 5))
    cont = est_sin["cont_tipo_caja"]          # (cajero, tipo) promedio por replica
    x = np.arange(4); width = 0.25
    for c in range(N_CAJEROS):
        ax.bar(x + (c - 1) * width, cont[c], width, label=f"Cajero {c+1}")
    ax.set_xticks(x); ax.set_xticklabels(TIPOS)
    ax.set_ylabel("Usuarios promedio por replica")
    ax.set_title("Fig 4. Promedio de usuarios por tipo en cada cajero")
    ax.legend(); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "fig4_usuarios_tipo.png"), dpi=120); plt.close(fig)

    # Fig 5: verificacion / calibracion (sim vs teorico)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    # 5a proporciones
    axes[0].bar(x - 0.2, PROB, 0.4, label="Objetivo", color="#3182bd")
    axes[0].bar(x + 0.2, est_sin["prop_tipo"], 0.4, label="Simulado", color="#fd8d3c")
    axes[0].set_xticks(x); axes[0].set_xticklabels(TIPOS)
    axes[0].set_title("Verificacion: proporcion de tipos")
    axes[0].set_ylabel("Proporcion"); axes[0].legend(); axes[0].grid(alpha=0.3, axis="y")
    # 5b servicio medio por tipo
    axes[1].bar(x - 0.2, SERV_MEAN, 0.4, label="Teorico", color="#3182bd")
    axes[1].bar(x + 0.2, est_sin["serv_tipo_mean"], 0.4, label="Simulado", color="#fd8d3c")
    axes[1].set_xticks(x); axes[1].set_xticklabels(TIPOS)
    axes[1].set_title("Calibracion: tiempo medio de servicio por tipo")
    axes[1].set_ylabel("Minutos"); axes[1].legend(); axes[1].grid(alpha=0.3, axis="y")
    fig.suptitle("Fig 5. Verificacion y calibracion del modelo")
    fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "fig5_verificacion.png"), dpi=120); plt.close(fig)

    # Fig 6: antes vs despues de eliminar transitorio
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = cajas
    xx = np.arange(N_CAJEROS)
    ax.bar(xx - 0.2, est_con["sis_caja_mean"], 0.4, label="Con transitorio", color="#bdbdbd")
    ax.bar(xx + 0.2, est_sin["sis_caja_mean"], 0.4, label="Sin transitorio", color="#08519c")
    ax.set_xticks(xx); ax.set_xticklabels(labels)
    ax.set_ylabel("W promedio en sistema (min)")
    ax.set_title("Fig 6. Tiempo en sistema por cajero: antes vs despues de eliminar transitorio")
    ax.legend(); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "fig6_antes_despues.png"), dpi=120); plt.close(fig)

    # ---- guardar resumen numerico ----
    import json
    resumen = dict(
        clientes_prom=float(np.mean([len(r) for r in replicas])),
        warmup=warmup, w_estable=float(w_final),
        serv_caja=[float(v) for v in est_sin["serv_caja_mean"]],
        sis_caja=[float(v) for v in est_sin["sis_caja_mean"]],
        esp_caja=[float(v) for v in est_sin["esp_caja_mean"]],
        cajero_menor=int(cmin) + 1, cajero_mayor=int(cmax) + 1,
        cont_tipo_total=[float(v) for v in est_sin["cont_tipo_caja"].sum(axis=0)],
        cont_tipo_caja=est_sin["cont_tipo_caja"].tolist(),
        serv_tipo=[float(v) for v in est_sin["serv_tipo_mean"]],
        prop_tipo=[float(v) for v in est_sin["prop_tipo"]],
        media_W_final=float(acum[-1]), ic_final=float(hw[-1]),
    )
    with open("resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return resumen


if __name__ == "__main__":
    main()
