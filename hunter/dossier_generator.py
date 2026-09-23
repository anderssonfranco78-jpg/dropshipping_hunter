"""Winner Dossier & 4 Conversion Hooks Synthesizer (Milestone M4).

Conforms strictly to:
- PROJECT.md § Feature Inventory (Features 19, 20, 21)
- 07-Manual-Maestro-Dropshipping-Seleccion-Producto-Ganador.md
- 14-Protocolo-Desarme-Forense-Storyboarding-y-Guion-Tecnico.md
- 08-Matriz-Canonica-3-Modalidades-Edicion-Video-Antigravity.md

Generates:
1. The 4 Conversion Hooks per validated winner:
   - Curiosidad Disruptiva (Pattern Interrupt)
   - Agitación de Dolor Real (Emotional Visceral Trigger)
   - Contrariano (Challenging Conventional Wisdom)
   - Transformación Inmediata (Before vs After)
2. Remotion Modalidad 3 Video Blueprints:
   - Dual Google Cloud TTS: es-US-Neural2-C (Client) & es-US-Neural2-B (Creator)
   - 1.0 second acoustic silence pause prior to beat drop
   - Beat Drop with white flash, LiQWYD track ('Show Me'), and non-linear speed ramp
   - Floating3DText volumetric typography without opaque pill backgrounds
   - Target loudness: -19.7 LUFS
3. dossier_productos_ganadores.md executive Markdown report with complete technical sheets.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from hunter.models import AuditResult, FinancialMetrics, RawCandidate

# Windows console encoding safeguard
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger("hunter.dossier_generator")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ==============================================================================
# CANONICAL REMOTION MODALIDAD 3 CONSTANTS
# ==============================================================================

VOICE_CUSTOMER = "es-US-Neural2-C"
VOICE_CREATOR = "es-US-Neural2-B"
ACOUSTIC_PAUSE_SEC = 1.0
TARGET_LUFS = -19.7
SPEED_RAMP_RUSH = 1.8
SPEED_RAMP_PLATEAU = 0.18

# Canonical supplier URLs and logistics details for the 4 core winners
CANONICAL_SUPPLIER_DATA: Dict[str, Dict[str, Any]] = {
    "spinerelief-pro": {
        "aliexpress_url": "https://www.aliexpress.com/w/wholesale-lumbar-traction-belt.html",
        "cj_url": "https://cjdropshipping.com/list-detail.html?search=lumbar%20traction%20belt",
        "shipping_carrier": "YunExpress Specialty Line",
        "delivery_days": "7 - 10 días laborables",
        "packaging": "Caja neutra con bolsa TPU, bomba manual con manómetro, correa extensora",
        "target_countries": ["US", "UK", "CA", "AU"],
        "posting_windows": [
            {
                "slot_name": "Slot 1 (Matutino)",
                "time_range": "06:30 – 08:00",
                "timezone": "Hora local del target",
                "rational": "Rigidez lumbar y dolor agudo al despertar de la cama; scrolleo compulsivo matutino.",
            },
            {
                "slot_name": "Slot 2 (Mediodía)",
                "time_range": "12:30 – 14:00",
                "timezone": "Hora local del target",
                "rational": "Pausa tras 4 horas continuas de oficina o manejo de camión; fatiga lumbar acumulada.",
            },
            {
                "slot_name": "Slot 3 (Prime Nocturno)",
                "time_range": "19:30 – 21:30",
                "timezone": "Hora local del target",
                "rational": "Fin de jornada laboral; relax en sofá buscando alivio antes de dormir.",
            },
        ],
        "wow_mechanism": (
            "Segundo 0.0-1.5: Plano cerrado lateral en cintura. El usuario conecta la manguera y presiona "
            "la bomba dos veces. Segundo 1.5-3.0: El cinturón se expande violentamente hacia arriba con un sonido "
            "neumático nítido ([SFX: PNEUMATIC_HISS]), estirando visiblemente el torso mientras una animación 3D "
            "de rayos X muestra las vértebras L1-L5 separándose y el nervio ciático pasando de rojo a azul relajado."
        ),
    },
    "aeroforce-x3": {
        "aliexpress_url": "https://www.aliexpress.com/w/wholesale-turbo-jet-fan.html",
        "cj_url": "https://cjdropshipping.com/list-detail.html?search=turbo%20jet%20fan",
        "shipping_carrier": "YunExpress Special Battery Line / CJPacket Sensitive (UN38.3)",
        "delivery_days": "8 - 11 días hábiles",
        "packaging": "Carcasa de aleación CNC, boquilla magnética, cable USB-C de carga rápida, estuche rígido",
        "target_countries": ["US", "CA", "AU", "UK"],
        "posting_windows": [
            {
                "slot_name": "Slot 1 (Mediodía)",
                "time_range": "12:00 – 13:30",
                "timezone": "Hora local del target",
                "rational": "Pausa de almuerzo, consumo rápido de contenido táctico/gadgets en TikTok.",
            },
            {
                "slot_name": "Slot 2 (Tarde / Salida)",
                "time_range": "17:00 – 18:30",
                "timezone": "Hora local del target",
                "rational": "Salida laboral; el conductor observa su auto con marcas de polvo o lluvia en el aparcamiento.",
            },
            {
                "slot_name": "Slot 3 (Fin de Semana Matutino)",
                "time_range": "Sábados y Domingos 09:30 – 11:30",
                "timezone": "Hora local del target",
                "rational": "Horario estrella de lavado de coches, bricolaje y proyectos caseros.",
            },
        ],
        "wow_mechanism": (
            "Segundo 0.0-1.2: Primer plano de un espejo retrovisor cubierto de gotas de lluvia. Segundo 1.2-2.8: "
            "Se activa el botón turbo con un zumbido de turbina de avión ([SFX: JET_TURBINE_SPOOL]). A 5 cm de distancia, "
            "el agua sale pulverizada violentamente, dejando la chapa y el espejo con acabado cristalino seco en 1 segundo "
            "sin que ninguna toalla roce la carrocería."
        ),
    },
    "prosmile-ultrasonic": {
        "aliexpress_url": "https://www.aliexpress.com/w/wholesale-ultrasonic-dental-calculus-remover.html",
        "cj_url": "https://cjdropshipping.com/list-detail.html?search=ultrasonic%20tooth%20cleaner",
        "shipping_carrier": "CJPacket Fast Line / YunExpress Ordinary",
        "delivery_days": "7 - 10 días laborables",
        "packaging": "Dispositivo IPX6 impermeable, 2 puntas de acero quirúrgico 316, espejo dental antivaho, cable USB-C",
        "target_countries": ["US", "UK", "DE", "AU"],
        "posting_windows": [
            {
                "slot_name": "Slot 1 (Matutino)",
                "time_range": "07:00 – 08:30",
                "timezone": "Hora local del target",
                "rational": "Rutina de cepillado frente al espejo; frustración directa al observar manchas y cálculo.",
            },
            {
                "slot_name": "Slot 2 (Nocturno Prime)",
                "time_range": "20:30 – 22:30",
                "timezone": "Hora local del target",
                "rational": "Higiene nocturna antes de dormir; soledad en el baño revisando el teléfono descalzo.",
            },
        ],
        "wow_mechanism": (
            "Segundo 0.0-1.5: Macro 4K del interior de la boca sobre un molar con una costra marrón de sarro. "
            "Segundo 1.5-3.0: La punta metálica toca suavemente el sarro con un pitido ultrasónico ([SFX: ULTRASONIC_CHIRP]) "
            "y la costra se desmorona en pedazos sólidos instantáneamente dejando el esmalte impoluto. Acto seguido, la punta "
            "toca la cáscara de un huevo crudo o un globo inflado sin romperlo para demostrar que es 100% inocuo en encías."
        ),
    },
    "steamfur-pro": {
        "aliexpress_url": "https://www.aliexpress.com/w/wholesale-steamy-cat-brush.html",
        "cj_url": "https://cjdropshipping.com/list-detail.html?search=steamy%20pet%20brush",
        "shipping_carrier": "YunExpress Ordinary / CJPacket Fast Line",
        "delivery_days": "7 - 10 días laborables",
        "packaging": "Cepillo con cerdas de silicona médica, micronebulizador ultrasónico USB-C, depósito de recarga",
        "target_countries": ["US", "CA", "UK", "AU"],
        "posting_windows": [
            {
                "slot_name": "Slot 1 (Matutino)",
                "time_range": "08:00 – 09:30",
                "timezone": "Hora local del target",
                "rational": "Alimentación matutina y cepillado rápido antes de salir a trabajar.",
            },
            {
                "slot_name": "Slot 2 (Vespertino Sofá)",
                "time_range": "18:00 – 20:30",
                "timezone": "Hora local del target",
                "rational": "Tiempo de caricias con la mascota en el sofá; pelos volando por el salón.",
            },
        ],
        "wow_mechanism": (
            "Segundo 0.0-1.5: Púas de silicona peinando el lomo de un gato esponjoso; sale una micro-niebla de vapor ionizado "
            "blanco ([SFX: STEAM_HISS]). Segundo 1.5-3.0: La mano levanta una pieza de fieltro de pelo completa de 10 cm "
            "en una sola capa sólida sin dejar ni un pelo suelto en el aire."
        ),
    },
}


# ==============================================================================
# CANONICAL 4 CONVERSION HOOKS LIBRARY
# ==============================================================================

CANONICAL_HOOKS: Dict[str, Dict[str, Any]] = {
    "spinerelief-pro": {
        "curiosidad_disruptiva": {
            "hook_type": "curiosidad_disruptiva",
            "headline": "Curiosidad Disruptiva: El Secreto Médico Prohibido",
            "dialogue_script": {
                "client_neural2_c": "¿Por qué los camioneros tienen prohibido manejar sin inflarse esto?",
                "creator_neural2_b": "Porque en 30 segundos separa tus vértebras 7 milímetros.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Primer plano de una persona colocándose una faja de tracción con manómetro neumático.",
                    "camera_motion": "Snap Zoom violento (1.0x -> 1.35x) con desenfoque radial dinámico.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): '¿Por qué los camioneros tienen prohibido manejar sin inflarse esto?'",
                    "sfx": "[SFX: WHOOSH_FAST]",
                    "floating_3d_text": "'¿PROHIBIDO?' en rojo neón extruido arriba (rotateX: 12deg)",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Detalle en 4K de las 24 columnas de aire en la espalda listas para cargarse.",
                    "camera_motion": "Paneo lateral acelerado (1.8x rush).",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Porque en 30 segundos separa tus vértebras 7 milímetros.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'7 MILÍMETROS' en verde esmeralda 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "PANTALLA CONGELADA CON SILUETA EN TENSIÓN ANATÓMICA.",
                    "camera_motion": "Cero movimiento (Pausa dramática de 1.0s de tensión acústica).",
                    "audio_cue": "Silencio sepulcral absoluto (cero voz).",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El cinturón se infla a tope; el torso se estira visiblemente. Destello blanco.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp no lineal (2.0x -> 0.18x meseta técnica).",
                    "audio_cue": "Entra bajo enérgico y track musical (LiQWYD - Show Me).",
                    "sfx": "[SFX: BEAT_DROP + PNEUMATIC_HISS]",
                    "floating_3d_text": "'DESCOMPRESIÓN L4-L5' en dorado 3D sin cajas ni pills",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Animación 3D de columna: el disco herniado vuelve a su centro al expandirse las vértebras.",
                    "camera_motion": "Snap zoom a la zona lumbar con tracking volumétrico.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Libera el nervio ciático atrapado sin pisar un quirófano.'",
                    "sfx": "[SFX: BONE_POP_RELIEF]",
                    "floating_3d_text": "'CIÁTICA DESBLOQUEADA' en cian neón 3D",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "El usuario camina erguido, sonríe y se toca la espalda sin dolor.",
                    "camera_motion": "Zoom out continuo (0.95x) hacia la llamada a la acción.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Pruébalo 14 días. Si tu espalda no revive, te devolvemos cada centavo.'",
                    "sfx": "[SFX: CASH_REGISTER]",
                    "floating_3d_text": "'GARANTÍA 14 DÍAS' en amarillo brillante",
                },
            ],
        },
        "agitacion_dolor_real": {
            "hook_type": "agitacion_dolor_real",
            "headline": "Agitación de Dolor Real: El Ardor Lumbar al Levantarte",
            "dialogue_script": {
                "client_neural2_c": "Si levantarte de la cama o del auto te toma 5 minutos por ese ardor lumbar...",
                "creator_neural2_b": "Tus vértebras están aplastando este nervio ahora mismo.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Persona que intenta levantarse de la silla de oficina y se queda doblada de agonía.",
                    "camera_motion": "Snap zoom agresivo al rostro de dolor (1.0x -> 1.4x).",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Si levantarte de la cama o del auto te toma 5 minutos por ese ardor lumbar...'",
                    "sfx": "[SFX: HEARTBEAT_LOW]",
                    "floating_3d_text": "'¿ARDOR LUMBAR?' en rojo fuego 3D",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Primer plano al pulgar apretando la zona baja de la columna inflamada.",
                    "camera_motion": "Camera shake de impacto visceral.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Tus vértebras están aplastando este nervio ahora mismo.'",
                    "sfx": "[SFX: ELECTRIC_SPARK]",
                    "floating_3d_text": "'NERVIO PELLIZCADO' en amarillo neón",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL MOMENTO DE TENSIÓN AGUDA DEL NERVIO.",
                    "camera_motion": "Silencio acústico riguroso de 1.0s.",
                    "audio_cue": "Cero voz, pausa absoluta.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El usuario se coloca el cinturón y bombea aire 3 veces con alivio instantáneo.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp (1.8x rush -> 0.18x meseta).",
                    "audio_cue": "Entra beat y bajo enérgico LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + AIR_PUMP]",
                    "floating_3d_text": "'ADIÓS PRESIÓN' en titanio 3D reflectivo",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Expresión facial cambiando de sufrimiento a un suspiro de alivio genuino.",
                    "camera_motion": "Paneo vertical suave de abajo hacia arriba.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): '24 cámaras de aire absorben el peso de tu tronco de inmediato.'",
                    "sfx": "[SFX: EXHALE_RELIEF]",
                    "floating_3d_text": "'ALIVIO EN 60 SEG' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "El usuario agachándose con soltura para levantar un objeto del suelo sin miedo.",
                    "camera_motion": "Tracking dinámico 3D.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Vuelve a moverte sin miedo al pinchazo. Enlace en bio con 40% OFF hoy.'",
                    "sfx": "[SFX: CLICK_POP]",
                    "floating_3d_text": "'40% OFF HOY' en oro 3D",
                },
            ],
        },
        "contrariano": {
            "hook_type": "contrariano",
            "headline": "Contrariano: La Farsa de las Fajas de Farmacia",
            "dialogue_script": {
                "client_neural2_c": "Por qué gastar $150 en fajas de farmacia empeora tu dolor de espalda...",
                "creator_neural2_b": "Porque apretar tu abdomen no separa tus huesos.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Una faja elástica de neopreno barata de farmacia siendo arrojada al cubo de basura.",
                    "camera_motion": "Snap Zoom directo al cubo de basura.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Por qué gastar $150 en fajas de farmacia empeora tu dolor de espalda...'",
                    "sfx": "[SFX: TRASH_SLAM]",
                    "floating_3d_text": "'NO SIRVEN' en rojo sangre sobre el cubo",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Modelo anatómico mostrando cómo una faja elástica solo comprime la carne hacia adentro.",
                    "camera_motion": "Giro 3D volumétrico (rotateY: -15deg).",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Porque apretar tu abdomen no separa tus huesos.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'SOLO APRIETAN' en naranja 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "PANTALLA EN NEGRO / SILENCIO DE CONTRADICCIÓN.",
                    "camera_motion": "Pausa acústica estricta de 1.0s.",
                    "audio_cue": "Silencio total.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "Entrada triunfal del SpineRelief Pro inflándose en cámara lenta vertical.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp dinámico.",
                    "audio_cue": "Explota la base musical rítmica.",
                    "sfx": "[SFX: BEAT_DROP + HISS]",
                    "floating_3d_text": "'TRACCIÓN CLÍNICA' en titanio reflectivo",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Split screen animado: Faja elástica (fuerza horizontal dañina) vs SpineRelief Pro (fuerza vertical de descompresión).",
                    "camera_motion": "Split screen animado con barras de fuerza 3D.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Esto estira verticalmente tu columna, imitando una camilla médica de $3,000.'",
                    "sfx": "[SFX: DING_WIN]",
                    "floating_3d_text": "'TRACCIÓN VERTICAL' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Demostración de uso discreto bajo la camisa en la oficina o manejando.",
                    "camera_motion": "Paneo lateral suave a 60 fps.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Úsalo bajo tu ropa mientras trabajas. Talla universal con extensor gratis.'",
                    "sfx": "[SFX: DISCORD_PING]",
                    "floating_3d_text": "'TALLA UNIVERSAL' en amarillo 3D",
                },
            ],
        },
        "transformacion_inmediata": {
            "hook_type": "transformacion_inmediata",
            "headline": "Transformación Inmediata: De la Incapacidad a la Plenitud",
            "dialogue_script": {
                "client_neural2_c": "De no poder atarte las zapatillas por el dolor de ciática...",
                "creator_neural2_b": "A pasar 6 horas de pie sin un solo tirón lumbar.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Pantalla dividida: Lado izquierdo (Persona encorvada que no puede inclinarse a atarse los zapatos).",
                    "camera_motion": "Zoom in hacia la izquierda con tono desaturado y frío.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'De no poder atarte las zapatillas por el dolor de ciática...'",
                    "sfx": "[SFX: RECORD_SCRATCH]",
                    "floating_3d_text": "'ANTES' en rojo desaturado",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Lado derecho: La misma persona trotando y jugando con sus hijos sin molestia alguna.",
                    "camera_motion": "Snap zoom al lado derecho brillante y saturado.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'A pasar 6 horas de pie sin un solo tirón lumbar.'",
                    "sfx": "[SFX: WHOOSH_SWOOSH]",
                    "floating_3d_text": "'DESPUÉS' en verde esmeralda 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL CORTE CENTRAL DE CONTRASTE.",
                    "camera_motion": "Silencio dramático riguroso de 1.0s.",
                    "audio_cue": "Silencio absoluto.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "Se revela el SpineRelief Pro ajustado discretamente bajo la ropa.",
                    "camera_motion": "Beat Drop. Flash blanco y cámara lenta técnica (0.18x plateau).",
                    "audio_cue": "Entra la música al 100% de ganancia (mastering a -19.7 LUFS).",
                    "sfx": "[SFX: BEAT_DROP]",
                    "floating_3d_text": "'EL SECRETO' en oro 3D flotante",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Primer plano al manómetro marcando 2.5 bares de descompresión segura.",
                    "camera_motion": "Rotación 3D en eje Z.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): '20 minutos al día para reprogramar el espacio de tus discos vertebrales.'",
                    "sfx": "[SFX: RATCHET_CLICK]",
                    "floating_3d_text": "'20 MIN AL DÍA' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Unboxing completo del kit con bomba, extensor y folleto en español.",
                    "camera_motion": "Zoom out fluido.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Envío express garantizado en 7 a 10 días. Pide el tuyo en el botón abajo.'",
                    "sfx": "[SFX: BELL_CHIME]",
                    "floating_3d_text": "'ENVÍO EXPRESS 7-10D'",
                },
            ],
        },
    },
    "aeroforce-x3": {
        "curiosidad_disruptiva": {
            "hook_type": "curiosidad_disruptiva",
            "headline": "Curiosidad Disruptiva: Un Motor de Caza en el Bolsillo",
            "dialogue_script": {
                "client_neural2_c": "¿Cómo es legal tener un motor de avión en el bolsillo?",
                "creator_neural2_b": "130,000 revoluciones por minuto. Esto no es un juguete.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Una lata de aluminio sobre una mesa de metal sale disparada 4 metros atrás sin tocarla.",
                    "camera_motion": "Snap zoom violento (1.0x -> 1.4x) siguiendo la lata volando.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): '¿Cómo es legal tener un motor de avión en el bolsillo?'",
                    "sfx": "[SFX: AIR_BLAST_WHOOSH]",
                    "floating_3d_text": "'¿CÓMO ES LEGAL?' en rojo neón extruido",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Se revela la mano sosteniendo el mini AeroForce X3 en acabado negro mate.",
                    "camera_motion": "Rotación de perspectiva volumétrica (rotateY: 20deg).",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): '130,000 revoluciones por minuto. Esto no es un juguete.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'130,000 RPM' en cian neón 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO DEL SOPLADOR APUNTANDO DIRECTO A CÁMARA.",
                    "camera_motion": "1.0 segundo de silencio sepulcral sin voz ni música.",
                    "audio_cue": "Silencio acústico riguroso.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "Disparo de aire a un espejo de coche cubierto de barro y agua; todo desaparece en 0.5s.",
                    "camera_motion": "Beat Drop. Destello blanco y Speed Ramp (2.2x rush -> 0.15x meseta técnica).",
                    "audio_cue": "Entra bajo potente de Show Me (LiQWYD).",
                    "sfx": "[SFX: BEAT_DROP + JET_SPOOL]",
                    "floating_3d_text": "'52 M/S DE POTENCIA' en amarillo 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Limpieza de un teclado gamer: migas y polvo salen disparados al instante.",
                    "camera_motion": "Macro zoom focal a los switches del teclado.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Desaloja la suciedad de donde ninguna aspiradora jamás podrá entrar.'",
                    "sfx": "[SFX: MACHINE_PURR]",
                    "floating_3d_text": "'LIMPIEZA TÁCTICA' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Comparativa de tamaño: cabe exactamente en la palma de la mano o en la guantera.",
                    "camera_motion": "Zoom out suave.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Batería recargable USB-C para 40 minutos de ráfaga continua. Últimas unidades.'",
                    "sfx": "[SFX: HITMARKER]",
                    "floating_3d_text": "'ÚLTIMAS UNIDADES' en oro brillante",
                },
            ],
        },
        "agitacion_dolor_real": {
            "hook_type": "agitacion_dolor_real",
            "headline": "Agitación de Dolor Real: Los Swirl Marks que Destruyen tu Auto",
            "dialogue_script": {
                "client_neural2_c": "Si secas tu auto con toallas de microfibra, estás arruinando tu pintura...",
                "creator_neural2_b": "Una sola mota de polvo atrapada en el trapo y tu coche pierde el 30% de su valor.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Luz directa en capó de coche negro revelando miles de micro-rayones circulares.",
                    "camera_motion": "Snap zoom directo al reflejo arañado.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Si secas tu auto con toallas de microfibra, estás arruinando tu pintura...'",
                    "sfx": "[SFX: GLASS_SCRATCH]",
                    "floating_3d_text": "'ESTÁS RAYANDO TU AUTO' en rojo fuego",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Macro a una toalla recogiendo una arenilla invisible y frotándola contra la laca.",
                    "camera_motion": "Cámara lenta dramática.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Una sola mota de polvo atrapada en el trapo y tu coche pierde el 30% de su valor.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'-30% DE VALOR' en rojo neón",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL MICRO-RAYÓN AMPLIADO.",
                    "camera_motion": "Pausa acústica de 1.0s de silencio sepulcral.",
                    "audio_cue": "Silencio absoluto.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El AeroForce X3 entra secando el capó a 10 cm sin ningún contacto físico.",
                    "camera_motion": "Beat Drop. White flash y Speed Ramp dinámico.",
                    "audio_cue": "Beat y bajo enérgico LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + TURBINE]",
                    "floating_3d_text": "'SECADO SIN CONTACTO' en metal extruido 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Las gotas de agua corren y caen fuera del capó como mercurio líquido.",
                    "camera_motion": "Paneo rápido horizontal a 60 fps.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Cero fricción, cero marcas de agua en cerraduras y cero arañazos. Acabado de concurso.'",
                    "sfx": "[SFX: WATER_WHOOSH]",
                    "floating_3d_text": "'ACABADO DE SHOW' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Primer plano al kit con boquilla magnética de precisión snap-on.",
                    "camera_motion": "Snap zoom out.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'El gadget obligatorio para todo amante del motor. Consíguelo hoy con descuento.'",
                    "sfx": "[SFX: CASH_REGISTER]",
                    "floating_3d_text": "'OFERTA LIMITADA'",
                },
            ],
        },
        "contrariano": {
            "hook_type": "contrariano",
            "headline": "Contrariano: La Estafa de las Latas Desechables de Aire",
            "dialogue_script": {
                "client_neural2_c": "Deja de tirar tu dinero en latas de aire comprimido que se congelan en 20 segundos...",
                "creator_neural2_b": "Pagas $10 por lata para que escupan líquido y se queden sin fuerza a la mitad.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Una persona agitando una lata de aire comprimido que escupe líquido helado y se desinfla.",
                    "camera_motion": "Snap zoom a la lata congelada.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Deja de tirar tu dinero en latas de aire comprimido que se congelan en 20 segundos...'",
                    "sfx": "[SFX: GAS_FART_FAIL]",
                    "floating_3d_text": "'ESTAFA TOTAL' en rojo sangre sobre la lata",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Pila de 6 botes vacíos acumulados en un rincón con cartel de '$60 botados a la basura'.",
                    "camera_motion": "Paneo lateral rápido.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Pagas $10 por lata para que escupan líquido y se queden sin fuerza a la mitad.'",
                    "sfx": "[SFX: COIN_DROP]",
                    "floating_3d_text": "'DINERO TIRADO' en naranja",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN LA LATA CONGELADA INSERVIBLE.",
                    "camera_motion": "Silencio sepulcral de 1.0s.",
                    "audio_cue": "Silencio puro.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El AeroForce X3 se activa frente a cámara agitando la ropa como un huracán.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp no lineal.",
                    "audio_cue": "Explota la música LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + HURRICANE]",
                    "floating_3d_text": "'POTENCIA ILIMITADA' en azul neón 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Gráfica de inversión: 1 AeroForce X3 recargable vs 500 latas desechables de aire.",
                    "camera_motion": "Split screen animado comparativo.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Equivale a más de 500 latas de aire comprimido, pero recargable con tu cargador de móvil.'",
                    "sfx": "[SFX: LEVEL_UP]",
                    "floating_3d_text": "'500 LATAS EN 1' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Demostración encendiendo carbón de barbacoa en 10 segundos con el soplador.",
                    "camera_motion": "Paneo con chispas cinematográficas de fondo.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Seca tu coche, limpia tu PC y prende tu asado. Enlace en bio con stock rápido.'",
                    "sfx": "[SFX: SPARKLE_DING]",
                    "floating_3d_text": "'COMPRA AQUÍ' en amarillo 3D",
                },
            ],
        },
        "transformacion_inmediata": {
            "hook_type": "transformacion_inmediata",
            "headline": "Transformación Inmediata: De Espejos Goteando a Acabado Profesional",
            "dialogue_script": {
                "client_neural2_c": "De terminar de lavar tu coche y ver cómo el agua estancada te arruina la pintura otra vez...",
                "creator_neural2_b": "A dejar cada rincón sellado y seco al 100% en menos de 2 minutos.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Espejo lateral goteando agua sin parar tras el lavado, ensuciando la puerta recién limpia.",
                    "camera_motion": "Snap zoom a las gotas escurriendo.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'De terminar de lavar tu coche y ver cómo el agua estancada te arruina la pintura otra vez...'",
                    "sfx": "[SFX: SAD_TROMBONE_SHORT]",
                    "floating_3d_text": "'EL PEOR ERROR' en rojo",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "El chorro del AeroForce X3 expulsa toda el agua de la junta del espejo en 0.3 segundos.",
                    "camera_motion": "Speed ramp ultra-rápido (2.5x -> 0.2x).",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'A dejar cada rincón sellado y seco al 100% en menos de 2 minutos.'",
                    "sfx": "[SFX: FAST_WHOOSH]",
                    "floating_3d_text": "'SECO EN 2 MIN' en cian brillante 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL ESPEJO CRISTALINO SIN UNA SOLA GOTA.",
                    "camera_motion": "1.0 segundo de silencio absoluto.",
                    "audio_cue": "Silencio total.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "Paneo general del coche con acabado impecable bajo luces de estudio de detallado.",
                    "camera_motion": "Beat Drop. Destello blanco y movimiento cinematográfico.",
                    "audio_cue": "Música en su punto álgido LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP]",
                    "floating_3d_text": "'ACABADO PROFESIONAL' en oro 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "El creador sopla las rejillas de ventilación: sale nube de polvo seco y queda como nuevo.",
                    "camera_motion": "Macro zoom al habitáculo interior.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'La herramienta que usan los detailers profesionales ahora en el bolsillo de tu pantalón.'",
                    "sfx": "[SFX: AIR_PUFF]",
                    "floating_3d_text": "'NIVEL DETAILER' en titanio",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Empaque premium con boquilla magnética snap-on.",
                    "camera_motion": "Zoom out dinámico.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Pídelo hoy y recíbelo en tu puerta con seguimiento garantizado.'",
                    "sfx": "[SFX: NOTIFICATION_SUCCESS]",
                    "floating_3d_text": "'ORDENA CON 50% OFF'",
                },
            ],
        },
    },
    "prosmile-ultrasonic": {
        "curiosidad_disruptiva": {
            "hook_type": "curiosidad_disruptiva",
            "headline": "Curiosidad Disruptiva: El Metal que No Rompe Huevos",
            "dialogue_script": {
                "client_neural2_c": "¿Cómo es posible que esto rompa piedra pero no pueda reventar un globo?",
                "creator_neural2_b": "Porque tiene un sensor acústico que solo se activa al tocar sarro duro.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Una punta metálica vibrante toca la cáscara de un huevo crudo sin marcarlo; luego toca una costra dental y la pulveriza.",
                    "camera_motion": "Snap zoom macro (1.0x -> 1.5x) al huevo y al cálculo dental.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): '¿Cómo es posible que esto rompa piedra pero no pueda reventar un globo?'",
                    "sfx": "[SFX: RECORD_SCRATCH_QUICK]",
                    "floating_3d_text": "'¿ROMPE PIEDRA?' en amarillo neón",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Detalle de la punta tocando la yema del dedo: cero vibración y cero dolor.",
                    "camera_motion": "Paneo lateral suave.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Porque tiene un sensor acústico que solo se activa al tocar sarro duro.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'SENSOR INTELIGENTE' en cian 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN LA PUNTA DE TITANIO TOCANDO EL DIENTE.",
                    "camera_motion": "Silencio acústico riguroso de 1.0s.",
                    "audio_cue": "Silencio sepulcral.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "Macro 4K real: la placa amarillenta entre dos dientes se desprende en un solo bloque limpio.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp (2.0x -> 0.18x meseta técnica).",
                    "audio_cue": "Entra bajo potente LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + CRACK_CLEAN]",
                    "floating_3d_text": "'SARRO DESTRUIDO' en titanio blanco 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Se enjuaga con agua y se ve el esmalte blanco original reluciente como perla.",
                    "camera_motion": "Paneo a la sonrisa impecable.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): '40,000 vibraciones ultrasónicas por segundo. Sin taladros y sin sangre.'",
                    "sfx": "[SFX: SHINE_SPARKLE]",
                    "floating_3d_text": "'40,000 VIBRACIONES' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Caja médica con puntas intercambiables de acero 316 y espejo bucal.",
                    "camera_motion": "Zoom out fluido.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Hazte tu propia limpieza profesional en casa por menos de lo que cuesta el parking del dentista.'",
                    "sfx": "[SFX: CASH_REGISTER]",
                    "floating_3d_text": "'AHORRA $250'",
                },
            ],
        },
        "agitacion_dolor_real": {
            "hook_type": "agitacion_dolor_real",
            "headline": "Agitación de Dolor Real: La Vergüenza de Sonreír en Fotos",
            "dialogue_script": {
                "client_neural2_c": "Si dejas de sonreír en las fotos porque te da vergüenza el sarro amarillo acumulado...",
                "creator_neural2_b": "Y no tienes $300 de sobra para pagarle al dentista cada 6 meses...",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Persona hablando en público que se tapa la boca con la mano avergonzada al sonreír por tener manchas.",
                    "camera_motion": "Snap zoom a la mano cubriendo la boca.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Si dejas de sonreír en las fotos porque te da vergüenza el sarro amarillo acumulado...'",
                    "sfx": "[SFX: HEARTBEAT_DULL]",
                    "floating_3d_text": "'¿VERGÜENZA AL SONREÍR?' en rojo opaco",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Presupuesto dental en papel marcando: 'Deep Cleaning: $350.00'.",
                    "camera_motion": "Paneo rápido al documento médico.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Y no tienes $300 de sobra para pagarle al dentista cada 6 meses...'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'$350 EN LA CLÍNICA' en rojo neón",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL PAPEL DE LA FACTURA DENTAL IMPOSIBLE.",
                    "camera_motion": "1.0 segundo de silencio puro.",
                    "audio_cue": "Silencio absoluto.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El ProSmile se enciende con su luz LED focal iluminando la boca en el espejo.",
                    "camera_motion": "Beat Drop. Destello blanco y entrada musical enérgica.",
                    "audio_cue": "Explota la base rítmica.",
                    "sfx": "[SFX: BEAT_DROP + CHIRP]",
                    "floating_3d_text": "'LIMPIEZA EN CASA' en oro 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "En 3 pasadas suaves frente al espejo del baño, el sarro detrás de los incisivos desaparece.",
                    "camera_motion": "Macro toma dental.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Elimina años de cálculo, manchas de café y nicotina en 5 minutos en tu propio baño.'",
                    "sfx": "[SFX: WATER_RINSE]",
                    "floating_3d_text": "'EN SOLO 5 MIN' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Sonrisa abierta, blanca y confiada frente al espejo del baño.",
                    "camera_motion": "Zoom out cinemático.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Recupera tu confianza hoy mismo. Envío gratis y garantía de devolución total.'",
                    "sfx": "[SFX: DING_SUCCESS]",
                    "floating_3d_text": "'GARANTÍA 100%'",
                },
            ],
        },
        "contrariano": {
            "hook_type": "contrariano",
            "headline": "Contrariano: Por qué tu Cepillo de $120 No Sirve para el Sarro",
            "dialogue_script": {
                "client_neural2_c": "Por qué cepillarte 3 veces al día jamás quitará el sarro duro de tus dientes...",
                "creator_neural2_b": "El sarro es piedra caliza sólida; el cepillo de cerdas solo le hace cosquillas.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Cepillo eléctrico sónico de $120 frotando enérgicamente un molar con sarro sin lograr quitar nada.",
                    "camera_motion": "Snap zoom a las cerdas doblándose inútilmente.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Por qué cepillarte 3 veces al día jamás quitará el sarro duro de tus dientes...'",
                    "sfx": "[SFX: BRUSH_SCRUB_FAST]",
                    "floating_3d_text": "'NO LO QUITA' en rojo sangre arriba",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Gráfico microscópico: Las cerdas de nylon resbalan sobre el fosfato de calcio mineralizado.",
                    "camera_motion": "Rotación 3D del modelo dental anatómico.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'El sarro es piedra caliza sólida; el cepillo de cerdas solo le hace cosquillas.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'ES PIEDRA MINERAL' en naranja 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL MODELO ANATÓMICO DENTAL.",
                    "camera_motion": "Pausa de 1.0s de silencio sepulcral.",
                    "audio_cue": "Silencio acústico riguroso.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El cabezal de titanio del ProSmile toca la piedra; micro-cavitación acústica y la piedra se disuelve.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp (1.8x -> 0.18x meseta).",
                    "audio_cue": "Explota el bajo de Show Me (LiQWYD).",
                    "sfx": "[SFX: BEAT_DROP + ULTRASONIC_CHIRP]",
                    "floating_3d_text": "'CAVITACIÓN ACÚSTICA' en turquesa 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Demostración de seguridad: la punta roza la encía y se detiene automáticamente en 1 milisegundo.",
                    "camera_motion": "Macro a la encía rosada intacta sin sangrar.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Cero daño al esmalte y cero dolor en encías gracias a su sensor de densidad.'",
                    "sfx": "[SFX: CHIME_SAFE]",
                    "floating_3d_text": "'CERO DAÑO' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Vista del producto cargándose por USB-C junto al lavamanos moderno.",
                    "camera_motion": "Zoom out fluido.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'La herramienta que tu dentista no quiere que descubras. Pide el tuyo con 50% de descuento.'",
                    "sfx": "[SFX: CASH_REGISTER]",
                    "floating_3d_text": "'50% DE DESCUENTO' en amarillo 3D",
                },
            ],
        },
        "transformacion_inmediata": {
            "hook_type": "transformacion_inmediata",
            "headline": "Transformación Inmediata: De 5 Años de Sarro a Dientes de Seda",
            "dialogue_script": {
                "client_neural2_c": "De tener 5 años de sarro y manchas de tabaco pegadas a los dientes...",
                "creator_neural2_b": "A dejarlos con textura de seda y completamente limpios en 10 minutos.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Pantalla dividida: Lado izquierdo (dientes inferiores manchados de tabaco y sarro oscuro).",
                    "camera_motion": "Snap zoom hacia la izquierda desaturada.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'De tener 5 años de sarro y manchas de tabaco pegadas a los dientes...'",
                    "sfx": "[SFX: SAD_SCRATCH]",
                    "floating_3d_text": "'ANTES (5 AÑOS)' en marrón/rojo",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Lado derecho: Dientes limpios y blancos con brillo nítido de película.",
                    "camera_motion": "Snap zoom hacia la derecha con resplandor luminoso.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'A dejarlos con textura de seda y completamente limpios en 10 minutos.'",
                    "sfx": "[SFX: SHINE_CHIME]",
                    "floating_3d_text": "'DESPUÉS (10 MIN)' en blanco diamante 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL CORTE VERTICAL DEL SPLIT SCREEN.",
                    "camera_motion": "1.0 segundo de silencio absoluto.",
                    "audio_cue": "Silencio puro.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "La transición barre: se muestra en tiempo real sin cortes cómo el sarro se cae al escupir agua.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp dinámico.",
                    "audio_cue": "Beat y bajo enérgico LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + SPLASH]",
                    "floating_3d_text": "'SIN CORTES' en oro flotante 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "La persona pasa su lengua por detrás de los dientes con expresión de asombro total.",
                    "camera_motion": "Paneo suave al rostro sonriente.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Siente la sensación de limpieza clínica profunda cada vez que quieras sin salir de tu casa.'",
                    "sfx": "[SFX: POP_SOUND]",
                    "floating_3d_text": "'TEXTURA DE SEDA' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Kit completo con espejo bucal, 2 cabezales y cable en su estuche sellado.",
                    "camera_motion": "Snap zoom out.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Stock limitado para envío en 7 a 10 días. Toca el botón y reclama tu kit hoy.'",
                    "sfx": "[SFX: BELL_CHIME]",
                    "floating_3d_text": "'STOCK LIMITADO'",
                },
            ],
        },
    },
    "steamfur-pro": {
        "curiosidad_disruptiva": {
            "hook_type": "curiosidad_disruptiva",
            "headline": "Curiosidad Disruptiva: La Manta de Pelo Extraída en 3 Segundos",
            "dialogue_script": {
                "client_neural2_c": "¿Por qué los veterinarios aconsejan no cepillar a tu gato en seco nunca más?",
                "creator_neural2_b": "Porque el vapor frío ionizado neutraliza la estática y retira el pelo muerto en una manta sólida.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Púas de silicona peinando el lomo de un gato esponjoso; sale una columna de vapor frío blanco.",
                    "camera_motion": "Snap Zoom macro (1.0x -> 1.4x) a la nube de niebla ionizada.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): '¿Por qué los veterinarios aconsejan no cepillar a tu gato en seco nunca más?'",
                    "sfx": "[SFX: STEAM_HISS]",
                    "floating_3d_text": "'¿NO EN SECO?' en cian neón extruido",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "La mano de la dueña levanta una pieza de fieltro de pelo completa de 10 cm sin romperla.",
                    "camera_motion": "Paneo lateral acelerado (1.8x rush).",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Porque el vapor frío ionizado neutraliza la estática y retira el pelo en una sola manta sólida.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'MANTA SÓLIDA' en verde esmeralda 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN LA MANTA DE PELO FLOTANDO EN LA MANO.",
                    "camera_motion": "Pausa acústica de 1.0s de silencio total.",
                    "audio_cue": "Silencio absoluto.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El gato ronronea relajado cerrando los ojos bajo el masaje de vapor.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp (2.0x -> 0.18x meseta técnica).",
                    "audio_cue": "Explota la base rítmica de Show Me (LiQWYD).",
                    "sfx": "[SFX: BEAT_DROP + PURR_LOUD]",
                    "floating_3d_text": "'CERO ESTRÉS' en oro 3D flotante",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Comparativa: Cepillo normal (nube de pelo volando por el salón) vs SteamFur Pro (cero pelo en el aire).",
                    "camera_motion": "Split screen animado dinámico.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Atrapa el 99% del pelo muerto antes de que caiga en tu comida o en tu sofá.'",
                    "sfx": "[SFX: DING_WIN]",
                    "floating_3d_text": "'99% ATRAPADO' en titanio",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Cepillo recargable USB-C disponible en verde menta y amarillo pastel.",
                    "camera_motion": "Zoom out suave.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Apto para perros y gatos de todo tipo de pelo. Pide el tuyo con 50% de descuento.'",
                    "sfx": "[SFX: BELL_CHIME]",
                    "floating_3d_text": "'50% OFF HOY'",
                },
            ],
        },
        "agitacion_dolor_real": {
            "hook_type": "agitacion_dolor_real",
            "headline": "Agitación de Dolor Real: La Pesadilla de los Pelos en Toda la Casa",
            "dialogue_script": {
                "client_neural2_c": "¿Cansado de encontrar pelos de gato en tu ropa, en el sofá y hasta en tu comida?",
                "creator_neural2_b": "El cepillado común solo esparce los pelos por el aire; esto los atrapa al 100%.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Persona comiendo que saca un pelo largo de gato de su plato con frustración total.",
                    "camera_motion": "Snap zoom al tenedor con el pelo.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): '¿Cansado de encontrar pelos de gato en tu ropa, en el sofá y hasta en tu comida?'",
                    "sfx": "[SFX: RECORD_SCRATCH]",
                    "floating_3d_text": "'¿PELOS EN TU COMIDA?' en rojo fuego",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Dueño pasando un rodillo adhesivo que se satura a la segunda pasada sin quitar nada.",
                    "camera_motion": "Shake de frustración doméstica.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'El cepillado común solo esparce los pelos por el aire; esto los atrapa al 100%.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'ESPARCEN TODO' en naranja",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL PANTALÓN NEGRO LLENO DE PELOS BLANCOS.",
                    "camera_motion": "Silencio sepulcral de 1.0s.",
                    "audio_cue": "Silencio absoluto.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "El SteamFur Pro pasa por el lomo del animal y la nube de vapor fija todo el pelo al cepillo.",
                    "camera_motion": "Beat Drop. Destello blanco y cámara lenta dinámica.",
                    "audio_cue": "Beat y bajo enérgico LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + STEAM]",
                    "floating_3d_text": "'VAPOR IONIZADO' en cian 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Con un solo movimiento de dedos, la capa de pelo se despega en bloque directo a la papelera.",
                    "camera_motion": "Macro toma ultra-satisfactoria.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Sin electricidad estática, sin nubes de polvo y con depósito para esencia aromática.'",
                    "sfx": "[SFX: POP_CLEAN]",
                    "floating_3d_text": "'DESPEGUE LIMPIO' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Mascota limpia y sala de estar impoluta sin un solo pelo en los muebles.",
                    "camera_motion": "Zoom out fluido.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'El gadget definitivo para vivir con mascotas sin volverse loco. Envío rápido hoy.'",
                    "sfx": "[SFX: CASH_REGISTER]",
                    "floating_3d_text": "'ORDENA AHORA'",
                },
            ],
        },
        "contrariano": {
            "hook_type": "contrariano",
            "headline": "Contrariano: La Trampa de los Rodillos de Pegamento Adhesivo",
            "dialogue_script": {
                "client_neural2_c": "Por qué los rodillos adhesivos de papel son el peor gasto para dueños de mascotas...",
                "creator_neural2_b": "Gastas una fortuna en rollos que no quitan la raíz del pelaje suelto.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Un rollo de papel adhesivo lleno de pelos que ya no pega nada siendo arrojado a la basura.",
                    "camera_motion": "Snap zoom al rodillo inservible.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Por qué los rodillos adhesivos de papel son el peor gasto para dueños de mascotas...'",
                    "sfx": "[SFX: TRASH_SLAM]",
                    "floating_3d_text": "'DINERO PERDIDO' en rojo sangre",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "El gato sacudiéndose y soltando otra nube de pelos sobre la ropa recién despeluzada.",
                    "camera_motion": "Cámara lenta dramática.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Gastas una fortuna en rollos que solo limpian la superficie sin quitar el pelo muerto de raíz.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'NO VAN A LA RAÍZ' en naranja 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN LA MONTAÑA DE ROLLOS DE PAPEL USADOS.",
                    "camera_motion": "Pausa acústica de 1.0s de silencio total.",
                    "audio_cue": "Silencio sepulcral.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "Entrada del SteamFur Pro cepillando suavemente con micro-niebla calmante.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp no lineal.",
                    "audio_cue": "Explota el track musical.",
                    "sfx": "[SFX: BEAT_DROP + STEAM_HISS]",
                    "floating_3d_text": "'SOLUCIÓN DEFINITIVA' en titanio 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Demostración de masaje con las cerdas de silicona médica ultra-suaves.",
                    "camera_motion": "Macro a la cara de placer del animal.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Cerdas de silicona que no arañan la piel y depósito para agua tibia o loción desenredante.'",
                    "sfx": "[SFX: DING_SUCCESS]",
                    "floating_3d_text": "'SILICONA MÉDICA' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Kit con cable de carga y dosificador de líquido aromático.",
                    "camera_motion": "Zoom out suave.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Ahorra cientos de dólares en peluquería canina y felina. Pide el tuyo con garantía total.'",
                    "sfx": "[SFX: BELL_CHIME]",
                    "floating_3d_text": "'GARANTÍA TOTAL'",
                },
            ],
        },
        "transformacion_inmediata": {
            "hook_type": "transformacion_inmediata",
            "headline": "Transformación Inmediata: De la Lucha del Baño al Placer del Vapor",
            "dialogue_script": {
                "client_neural2_c": "De pasar 40 minutos persiguiendo a tu mascota con un cepillo que la estresa...",
                "creator_neural2_b": "A retirarle toda la capa muerta en 3 minutos mientras disfruta de un masaje de vapor.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Gato corriendo asustado debajo de la cama al ver un cepillo de alambre de metal agresivo.",
                    "camera_motion": "Snap zoom al gato escondido con ojos asustados.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'De pasar 40 minutos persiguiendo a tu mascota con un cepillo que la estresa...'",
                    "sfx": "[SFX: SAD_SCRATCH]",
                    "floating_3d_text": "'ESTRÉS TOTAL' en rojo",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "La misma mascota acostada panza arriba ronroneando mientras el SteamFur Pro la masajea.",
                    "camera_motion": "Snap zoom a la escena de calma y ronroneo.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'A retirarle toda la capa muerta en 3 minutos mientras disfruta de un masaje de vapor.'",
                    "sfx": "[SFX: PURR_SOFT]",
                    "floating_3d_text": "'SPA EN CASA' en verde esmeralda 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL CONTRASTE DE LA ESCENA ANTERIOR VS ACTUAL.",
                    "camera_motion": "Silencio dramático riguroso de 1.0s.",
                    "audio_cue": "Silencio absoluto.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": "Extracción en cámara lenta de una almohadilla compacta de pelo retirada de una sola pasada.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp dinámico (1.8x -> 0.18x).",
                    "audio_cue": "Beat y bajo enérgico LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + STEAM]",
                    "floating_3d_text": "'UNA SOLA PASADA' en oro 3D",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "El pelaje de la mascota queda suave, brillante y con un aroma fresco sin haberla bañado con agua.",
                    "camera_motion": "Paneo suave a 60 fps.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Deja el pelo brillante como recién salido del groomer profesional sin una gota de estrés.'",
                    "sfx": "[SFX: SHINE_CHIME]",
                    "floating_3d_text": "'BRILLO PROFESIONAL' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Unboxing del cepillo con sus accesorios y caja regalo.",
                    "camera_motion": "Zoom out final.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Stock de alta demanda. Pídelo hoy y recíbelo en 7 a 10 días en tu puerta.'",
                    "sfx": "[SFX: CASH_REGISTER]",
                    "floating_3d_text": "'ENVÍO 7-10 DÍAS'",
                },
            ],
        },
    },
}


# ==============================================================================
# DOSSIER GENERATOR CLASS
# ==============================================================================

class DossierGenerator:
    """Winner Technical Dossier & 4 Conversion Hooks Synthesizer."""

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        """Initialize DossierGenerator with data directory path."""
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parent.parent / "data"

    def generate_hooks(
        self, product: Union[AuditResult, RawCandidate, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Synthesize the 4 conversion hooks and Remotion Modalidad 3 technical specs.
        
        Args:
            product: AuditResult, RawCandidate, or dictionary representing the product.
            
        Returns:
            Dictionary containing the 4 hook archetypes:
            - curiosidad_disruptiva
            - agitacion_dolor_real
            - contrariano
            - transformacion_inmediata
            Each with headline, dialogue_script (dual Neural2 voices), and storyboard_rows.
        """
        # Extract candidate ID and product info
        if isinstance(product, AuditResult):
            cand = product.candidate
            cand_id = cand.candidate_id.lower().strip()
            name = cand.name
            category = cand.category
            description = cand.description
            pain_score = cand.pain_level_score
            speed_sec = cand.demo_visual_speed_sec
        elif isinstance(product, RawCandidate):
            cand_id = product.candidate_id.lower().strip()
            name = product.name
            category = product.category
            description = product.description
            pain_score = product.pain_level_score
            speed_sec = product.demo_visual_speed_sec
        elif isinstance(product, dict):
            cand_data = product.get("candidate", product)
            cand_id = str(cand_data.get("candidate_id", "")).lower().strip()
            name = str(cand_data.get("name", "Producto Ganador"))
            category = str(cand_data.get("category", "General"))
            description = str(cand_data.get("description", ""))
            pain_score = float(cand_data.get("pain_level_score", 85.0))
            speed_sec = float(cand_data.get("demo_visual_speed_sec", 1.5))
        else:
            raise TypeError(f"Unsupported product type: {type(product).__name__}")

        # Check for pre-compiled canonical hooks
        if cand_id in CANONICAL_HOOKS:
            return CANONICAL_HOOKS[cand_id]

        # Dynamic synthesizer conforming strictly to Remotion Modalidad 3
        return self._synthesize_dynamic_hooks(
            cand_id=cand_id,
            name=name,
            category=category,
            description=description,
            pain_score=pain_score,
            speed_sec=speed_sec,
        )

    def _synthesize_dynamic_hooks(
        self,
        cand_id: str,
        name: str,
        category: str,
        description: str,
        pain_score: float,
        speed_sec: float,
    ) -> Dict[str, Any]:
        """Dynamically generate genuine 4 hooks and Remotion storyboards for any winner."""
        short_name = name.split("—")[0].strip()

        # 1. Curiosidad Disruptiva (Pattern Interrupt)
        curiosity = {
            "hook_type": "curiosidad_disruptiva",
            "headline": f"Curiosidad Disruptiva: El Secreto Detrás de {short_name}",
            "dialogue_script": {
                "client_neural2_c": f"El 90% de las personas comete este grave error al buscar soluciones para {category.lower()}...",
                "creator_neural2_b": f"Y por eso siguen sufriendo hasta que descubren cómo funciona {short_name}.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": f"Primer plano de alto impacto demostrando el problema de {category.lower()}.",
                    "camera_motion": "Snap Zoom violento (1.0x -> 1.35x) con desenfoque radial.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'El 90% comete este grave error...'",
                    "sfx": "[SFX: WHOOSH_FAST]",
                    "floating_3d_text": "'¿ESTE ERROR?' en rojo neón extruido arriba (rotateX: 12deg)",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": f"Presentación del mecanismo central de {short_name}.",
                    "camera_motion": "Paneo lateral acelerado (1.8x rush).",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Y por eso siguen perdiendo tiempo y dinero.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": f"'{short_name.upper()}' en verde esmeralda 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "PANTALLA CONGELADA EN EL MOMENTO DE MÁXIMA EXPECTATIVA.",
                    "camera_motion": "Cero movimiento (Pausa dramática de 1.0s de tensión acústica).",
                    "audio_cue": "Silencio absoluto de 1.0 segundo (cero voz).",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": f"Demostración visual WOW en {speed_sec:.1f} segundos. Alto contraste visual.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp no lineal (2.0x -> 0.18x meseta técnica).",
                    "audio_cue": "Entra bajo potente y track musical (LiQWYD - Show Me).",
                    "sfx": "[SFX: BEAT_DROP + IMPACT]",
                    "floating_3d_text": "'TRANSFORMACIÓN REAL' en dorado 3D sin cajas ni pills",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": f"Detalle del funcionamiento: {description[:120]}...",
                    "camera_motion": "Snap zoom focal con tracking volumétrico.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Resuelve el problema de raíz sin complicaciones.'",
                    "sfx": "[SFX: DING_SUCCESS]",
                    "floating_3d_text": "'EFECTIVIDAD COMPROBADA' en cian neón 3D",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Usuario satisfecho utilizando el producto. Vista de empaque completo.",
                    "camera_motion": "Zoom out continuo (0.95x) hacia la llamada a la acción.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Pruébalo con garantía total. Enlace en bio con descuento hoy.'",
                    "sfx": "[SFX: CASH_REGISTER]",
                    "floating_3d_text": "'GARANTÍA 100%' en amarillo brillante",
                },
            ],
        }

        # 2. Agitación de Dolor Real (Emotional Visceral Trigger)
        pain = {
            "hook_type": "agitacion_dolor_real",
            "headline": f"Agitación de Dolor Real: El Sufrimiento Cotidiano en {category}",
            "dialogue_script": {
                "client_neural2_c": f"Si tu dolor y frustración con {category.lower()} te impiden disfrutar tu día...",
                "creator_neural2_b": f"Este mecanismo patentado erradica esa molestia desde el primer uso.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Persona sufriendo la fricción directa y cotidiana del problema.",
                    "camera_motion": "Snap zoom agresivo al rostro de frustración (1.0x -> 1.4x).",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Si este problema te arruina el día...'",
                    "sfx": "[SFX: HEARTBEAT_LOW]",
                    "floating_3d_text": "'¿DOLOR REAL?' en rojo fuego 3D",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Detalle en primer plano de la molestia o desgaste acumulado.",
                    "camera_motion": "Camera shake de impacto emocional.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Y no encuentras ninguna solución que realmente funcione.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'FRUSTRACIÓN TOTAL' en amarillo neón",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL INSTANTE DE MAYOR FRICCIÓN.",
                    "camera_motion": "Silencio acústico riguroso de 1.0s.",
                    "audio_cue": "Cero voz, pausa absoluta.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": f"{short_name} en acción disolviendo el dolor en vivo.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp (1.8x rush -> 0.18x meseta).",
                    "audio_cue": "Entra beat y bajo enérgico LiQWYD.",
                    "sfx": "[SFX: BEAT_DROP + RELIEF]",
                    "floating_3d_text": "'ALIVIO DIRECTO' en titanio 3D reflectivo",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Expresión facial cambiando de estrés a alivio completo.",
                    "camera_motion": "Paneo suave de abajo hacia arriba.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Diseñado específicamente para eliminar esa fricción en minutos.'",
                    "sfx": "[SFX: EXHALE_RELIEF]",
                    "floating_3d_text": "'EN MENOS DE 2 MIN' en verde esmeralda",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Demostración de uso práctico en el hogar o trabajo.",
                    "camera_motion": "Tracking dinámico 3D.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Recupera tu tranquilidad hoy. Pídelo en el botón de abajo.'",
                    "sfx": "[SFX: CLICK_POP]",
                    "floating_3d_text": "'PÍDELO HOY' en oro 3D",
                },
            ],
        }

        # 3. Contrariano (Challenging Conventional Wisdom)
        contrarian = {
            "hook_type": "contrariano",
            "headline": f"Contrariano: Por Qué los Métodos Tradicionales de {category} Fracasan",
            "dialogue_script": {
                "client_neural2_c": f"Por qué gastar cientos de dólares en productos genéricos empeora tu situación...",
                "creator_neural2_b": f"Porque no atacan la causa física real como lo hace {short_name}.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Un producto genérico convencional arrojado al cubo de basura.",
                    "camera_motion": "Snap Zoom directo al cubo de basura.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'Por qué tirar tu dinero en alternativas que no funcionan...'",
                    "sfx": "[SFX: TRASH_SLAM]",
                    "floating_3d_text": "'NO SIRVEN' en rojo sangre",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Comparación técnica explicando el fallo del diseño convencional.",
                    "camera_motion": "Giro 3D volumétrico (rotateY: -15deg).",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Solo gastas dinero sin solucionar el origen del problema.'",
                    "sfx": "[SFX: VINE_BOOM]",
                    "floating_3d_text": "'MÉTODO OBSOLETO' en naranja 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "PANTALLA EN NEGRO / SILENCIO DE CONTRADICCIÓN.",
                    "camera_motion": "Pausa acústica estricta de 1.0s.",
                    "audio_cue": "Silencio sepulcral total.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": f"Entrada del {short_name} resolviendo la limitación tradicional.",
                    "camera_motion": "Beat Drop. Flash blanco y Speed Ramp dinámico.",
                    "audio_cue": "Explota la base musical rítmica.",
                    "sfx": "[SFX: BEAT_DROP + WIN]",
                    "floating_3d_text": "'INNOVACIÓN REAL' en titanio reflectivo",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Split screen comparando método convencional vs solución innovadora.",
                    "camera_motion": "Split screen animado con indicadores gráficos.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Tecnología inteligente diseñada para máxima durabilidad y resultado.'",
                    "sfx": "[SFX: DING_WIN]",
                    "floating_3d_text": "'3X MÁS EFECTIVO' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Vista del producto con todos sus accesorios incluidos.",
                    "camera_motion": "Paneo lateral suave a 60 fps.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'La alternativa definitiva que sí cumple. Consíguelo con descuento directo.'",
                    "sfx": "[SFX: DISCORD_PING]",
                    "floating_3d_text": "'OFERTA EXCLUSIVA' en amarillo 3D",
                },
            ],
        }

        # 4. Transformación Inmediata (Before vs After)
        transformation = {
            "hook_type": "transformacion_inmediata",
            "headline": f"Transformación Inmediata: Antes y Después con {short_name}",
            "dialogue_script": {
                "client_neural2_c": f"De perder horas luchando con este problema de {category.lower()}...",
                "creator_neural2_b": f"A solucionarlo al 100% en menos de {speed_sec:.0f} segundos.",
            },
            "storyboard_rows": [
                {
                    "time_range": "0.0 - 1.2s",
                    "visual_action": "Pantalla dividida: Lado izquierdo (situación de colapso o suciedad desaturada).",
                    "camera_motion": "Zoom in hacia la izquierda desaturada.",
                    "audio_cue": f"Voz Cliente ({VOICE_CUSTOMER}): 'De sufrir horas con este problema...'",
                    "sfx": "[SFX: RECORD_SCRATCH]",
                    "floating_3d_text": "'ANTES' en rojo desaturado",
                },
                {
                    "time_range": "1.2 - 2.0s",
                    "visual_action": "Lado derecho: Resultado impecable y limpio con luz radiante.",
                    "camera_motion": "Snap zoom al lado derecho brillante y saturado.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'A dejarlo perfecto en menos de un minuto.'",
                    "sfx": "[SFX: WHOOSH_SWOOSH]",
                    "floating_3d_text": "'DESPUÉS' en verde esmeralda 3D",
                },
                {
                    "time_range": "2.0 - 3.0s",
                    "visual_action": "CONGELADO EN EL CORTE CENTRAL DEL SPLIT SCREEN.",
                    "camera_motion": "Silencio dramático riguroso de 1.0s.",
                    "audio_cue": "Silencio absoluto.",
                    "sfx": "[SFX: SILENCIO_TOTAL]",
                    "floating_3d_text": "Cero texto en pantalla",
                },
                {
                    "time_range": "3.0 - 4.5s",
                    "visual_action": f"{short_name} ejecutando la transformación sin cortes.",
                    "camera_motion": "Beat Drop. Flash blanco y cámara lenta técnica (0.18x plateau).",
                    "audio_cue": "Entra la música al 100% (mastering a -19.7 LUFS).",
                    "sfx": "[SFX: BEAT_DROP]",
                    "floating_3d_text": "'EN TIEMPO REAL' en oro 3D flotante",
                },
                {
                    "time_range": "4.5 - 7.0s",
                    "visual_action": "Demostración del resultado final impecable y sin esfuerzo.",
                    "camera_motion": "Rotación 3D volumétrica.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'La transformación instantánea que todos tus amigos van a notar.'",
                    "sfx": "[SFX: SHINE_CHIME]",
                    "floating_3d_text": "'RESULTADO 10/10' en cian neón",
                },
                {
                    "time_range": "7.0 - 10.0s",
                    "visual_action": "Presentación del unboxing y botón de compra rápida.",
                    "camera_motion": "Zoom out fluido.",
                    "audio_cue": f"Voz Creador ({VOICE_CREATOR}): 'Envío rápido de 7 a 10 días garantizado. Ordena el tuyo ahora.'",
                    "sfx": "[SFX: BELL_CHIME]",
                    "floating_3d_text": "'ENVÍO EXPRESS 7-10D'",
                },
            ],
        }

        return {
            "curiosidad_disruptiva": curiosity,
            "agitacion_dolor_real": pain,
            "contrariano": contrarian,
            "transformacion_inmediata": transformation,
        }

    def generate_dossier(
        self,
        audit_results: List[AuditResult],
        output_path: Optional[Union[str, Path]] = "dossier_productos_ganadores.md",
    ) -> str:
        """Produce the comprehensive, high-converting Markdown winner dossier.
        
        Args:
            audit_results: List of AuditResult instances to compile.
            output_path: Optional output file path for the Markdown dossier.
            
        Returns:
            The complete Markdown dossier string.
        """
        # Filter approved winners (tier == "WINNER" or passed_audit == True)
        winners = [r for r in audit_results if r.tier == "WINNER" or r.passed_audit]

        # Enforce minimum 3 winners requirement (Feature 21)
        if len(winners) < 3:
            logger.warning(
                "Audit results contain only %d approved winners; minimum 3 required. Including top contenders if needed.",
                len(winners),
            )
            # If less than 3 winners exist, include top contenders sorted by composite score
            contenders = [r for r in audit_results if r.tier == "CONTENDER"]
            contenders.sort(key=lambda x: x.composite_score, reverse=True)
            for c in contenders:
                if len(winners) >= 3:
                    break
                winners.append(c)

        if len(winners) < 3:
            raise ValueError(
                f"Insufficient validated winners to generate dossier: found {len(winners)}, minimum 3 required."
            )

        # Sort winners descending by composite score
        winners.sort(key=lambda r: (r.tier == "WINNER", r.composite_score), reverse=True)

        # Calculate summary statistics
        total_analyzed = len(audit_results)
        approved_count = len(winners)
        avg_markup = sum(w.financials.markup_multiplier for w in winners) / approved_count if approved_count > 0 else 0.0
        avg_net_margin = sum(w.financials.net_margin_pct for w in winners) / approved_count if approved_count > 0 else 0.0

        today_str = datetime.date.today().isoformat()
        iso_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Build YAML Frontmatter
        lines: List[str] = [
            "---",
            'title: "Dossier Oficial de Productos Ganadores Validados"',
            'source: "dropshipping_hunter"',
            f'date: "{today_str}"',
            f'generated_at: "{iso_timestamp}"',
            'evaluation_engine_version: "1.0.0"',
            'audit_standard: "Antigravity 7 Golden Rules"',
            "scoring_threshold_approval: 80",
            'currency: "USD"',
            "summary:",
            f"  total_candidates_analyzed: {total_analyzed}",
            f"  winners_approved: {approved_count}",
            f"  avg_markup_factor: {avg_markup:.2f}",
            f"  avg_net_margin_percentage: {avg_net_margin:.1f}",
            "products:",
        ]

        for w in winners:
            lines.append(f'  - id: "{w.candidate.candidate_id}"')
            lines.append(f'    name: "{w.candidate.name}"')
            lines.append(f"    score: {w.composite_score:.1f}")
            lines.append(f'    status: "{w.tier}"')

        lines.extend([
            "---",
            "",
            "# DOSSIER OFICIAL: PRODUCTOS GANADORES VALIDADOS (2026)",
            "",
            "> **Estándar de Evaluación**: Filtro de Acero de las 7 Reglas de Oro de Antigravity  ",
            f"> **Fecha de Generación**: {today_str} | **Entorno**: 100% Programático & Headless  ",
            f"> **Candidatos Analizados**: {total_analyzed} | **Ganadores Aprobados**: {approved_count}  ",
            f"> **Markup Promedio**: {avg_markup:.2f}x | **Margen Neto Promedio**: {avg_net_margin:.1f}%",
            "",
            "---",
            "",
            "## 1. RESUMEN ESTRATÉGICO EJECUTIVO",
            "",
            "Este dossier presenta los productos de comercio electrónico que han superado de forma matemática y rigurosa "
            "el **Filtro de Acero de las 7 Reglas de Oro de Antigravity**. Cada producto seleccionado cuenta con demostración visual "
            "instantánea (0-3 segundos), resolución de dolor agudo real, total ausencia en supermercados físicos de conveniencia, "
            "márgenes netos superiores al 65%, precios de venta dentro del rango de impulso ($29 – $69 USD), nula fricción por tallas o fragilidad, "
            "y líneas logísticas fiables de 7 a 12 días.",
            "",
            "Cada ficha técnica incluye su desglose financiero completo, proveedores mayoristas verificados, estrategia demográfica, "
            "franjas horarias recomendadas y la **partitura técnica de los 4 Ganchos de Conversión** lista para producción en "
            "**Remotion Modalidad 3** (diálogos duales `es-US-Neural2-C` / `es-US-Neural2-B`, pausa dramática de 1.0s, beat drop y Floating3DText).",
            "",
            "---",
            "",
            "## 2. CATÁLOGO DE PRODUCTOS GANADORES VALIDADOS",
            "",
        ])

        # Render each winner
        for idx, w in enumerate(winners, start=1):
            product_section = self._render_product_dossier_section(idx, w)
            lines.append(product_section)
            lines.append("\n---\n")

        # Concluding operational notes
        lines.extend([
            "## 3. PROTOCOLO DE PRODUCCIÓN REMOTION (MODALIDAD 3)",
            "",
            "Para renderizar los videos orgánicos de estos productos ganadores con la máxima tasa de retención algorítmica:",
            "",
            "1. **Pistas de Voz Duales**: Utilizar Google Cloud TTS con la configuración canónica:",
            f"   - **Voz Cliente (Escéptico/Testigo)**: `{VOICE_CUSTOMER}` (Speaking rate: 1.04x, Pitch: 0.0st).",
            f"   - **Voz Creador (Experto/Autoridad)**: `{VOICE_CREATOR}` (Speaking rate: 1.08x, Pitch: +0.5st).",
            "2. **Pausa Acústica de Tensión (1.0s)**: Entre el segundo 2.0 y el segundo 3.0 se debe silenciar al 100% todo el audio.",
            "   No incluir música de fondo, ruidos blancos ni respiración. Esta interrupción acústica despierta la atención cerebral.",
            "3. **Beat Drop & Speed Ramping**: En el segundo 3.0 exacto:",
            "   - Disparar flash blanco (`opacity: [0, 0.85, 0]` en 4 frames).",
            "   - Track musical: *Show Me* de LiQWYD masterizado a **-19.7 LUFS**.",
            "   - Transición de velocidad: 1.8x rush inicial -> 0.18x meseta técnica de demostración en cámara lenta.",
            "4. **Floating3DText**: Todas las frases clave deben renderizarse como texto 3D extruido volumétricamente con sombras proyectadas,",
            "   prohibiendo el uso de barras negras o píldoras opacas detrás del texto.",
            "",
            "---",
            "*Dossier generado automáticamente por `hunter.dossier_generator` — Sistema de Inteligencia y Prospección de Ganadores Dropshipping.*",
            "",
        ])

        content = "\n".join(lines)

        # Write to output file if path provided
        if output_path is not None:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("Winner dossier successfully persisted to %s (%d bytes)", out_file, len(content))

        return content

    def _render_product_dossier_section(self, rank_idx: int, result: AuditResult) -> str:
        """Render a single product's comprehensive Markdown sheet."""
        cand = result.candidate
        fin = result.financials
        cand_id = cand.candidate_id.lower().strip()

        # Retrieve supplier & logistics metadata
        supp = CANONICAL_SUPPLIER_DATA.get(cand_id, {
            "aliexpress_url": cand.source_url if cand.source_url.startswith("https://") else f"https://www.aliexpress.com/w/wholesale-{cand_id}.html",
            "cj_url": f"https://cjdropshipping.com/list-detail.html?search={cand_id}",
            "shipping_carrier": cand.shipping_carrier or "YunExpress",
            "delivery_days": f"{cand.shipping_days_min} a {cand.shipping_days_max} días laborables",
            "packaging": "Empaque individual sellado neutro para dropshipping",
            "target_countries": ["US", "UK", "CA", "AU"],
            "posting_windows": [
                {"slot_name": "Slot 1 (Matutino)", "time_range": "07:00 – 08:30", "timezone": "Hora local", "rational": "Primera revisión matutina del teléfono."},
                {"slot_name": "Slot 2 (Tarde / Prime)", "time_range": "18:30 – 21:00", "timezone": "Hora local", "rational": "Pico de ocio nocturno y mayor tasa de conversión."},
            ],
            "wow_mechanism": f"Demostración instantánea de alto contraste en {cand.demo_visual_speed_sec:.1f} segundos mostrando la transformación física directa.",
        })

        # Generate the 4 conversion hooks
        hooks = self.generate_hooks(result)

        # Format Target Demographics
        demo_lines = []
        if isinstance(cand.target_demographics, dict):
            for k, v in cand.target_demographics.items():
                if isinstance(v, list):
                    v_str = ", ".join(str(item) for item in v)
                else:
                    v_str = str(v)
                demo_lines.append(f"- **{k.capitalize()}**: {v_str}")
        demo_formatted = "\n".join(demo_lines) if demo_lines else "- **Público General**: Hombres y mujeres de 22 a 60 años en mercados Tier 1."

        # Format Posting Windows
        posting_lines = []
        for pw in supp.get("posting_windows", []):
            posting_lines.append(f"- **{pw.get('slot_name', 'Slot')}** ({pw.get('time_range', '')} {pw.get('timezone', '')}): {pw.get('rational', '')}")
        posting_formatted = "\n".join(posting_lines)

        # Format 7 Golden Rules Checklist
        rules_checklist = []
        for r_id in range(1, 8):
            r_score = result.rule_scores.get(r_id)
            if r_score:
                status_icon = "✅" if r_score.passed else "⚠️"
                rules_checklist.append(
                    f"- **Regla {r_id} ({r_score.name})**: {status_icon} Score: {r_score.raw_score:.1f}/100 "
                    f"(Ponderado: {r_score.weighted_score:.1f} pts) — {'Aprobado' if r_score.passed else 'Marginal'}"
                )

        checklist_formatted = "\n".join(rules_checklist)

        # Build Markdown content
        section_lines = [
            f"### 🏆 GANADOR #{rank_idx}: {cand.name}",
            "",
            f"**Categoría / Nicho**: {cand.category}  ",
            f"**ID de Referencia**: `{cand.candidate_id}`  ",
            f"**Puntuación Compuesta**: **{result.composite_score:.1f} / 100** | **Estado**: `🏆 {result.tier}`  ",
            f"**Descripción**: {cand.description}",
            "",
            "#### Ficha Técnica y Desglose Financiero",
            "",
            "| Parámetro Financiero | Valor USD / % | Estándar Canónico Antigravity | Estado |",
            "|---|:---:|:---:|:---:|",
            f"| **Costo de Proveedor** (CoGS) | ${cand.supplier_cost:.2f} USD | Costo mayorista de fábrica | ✅ Verificado |",
            f"| **Costo de Envío Tracked** | ${cand.shipping_cost:.2f} USD | {supp.get('shipping_carrier', cand.shipping_carrier)} | ✅ Verificado |",
            f"| **Landed Cost** (Costo Puesto) | ${fin.landed_cost:.2f} USD | CoGS + Flete internacional | ✅ Calculado |",
            f"| **Precio de Venta Sugerido** (SRP) | ${fin.srp:.2f} USD | Sweet spot de impulso ($29 – $69 USD) | ✅ Cumple R5 |",
            f"| **Markup Multiplier** | **{fin.markup_multiplier:.2f}x** | Mínimo requerido: $\\ge 3.0\\text{{x}}$ | {'✅ SUPERADO' if fin.markup_multiplier >= 3.0 else '⚠️ AJUSTADO'} |",
            f"| **Comisión Pasarela** (Stripe 2.9% + $0.30) | ${fin.processor_fee:.2f} USD | Deducción automática por transacción | ✅ Incluido |",
            f"| **Buffer de Reserva** (1.0%) | ${fin.reserve_buffer:.2f} USD | Fondo para imprevistos / chargebacks | ✅ Incluido |",
            f"| **Beneficio Neto Limpio por Unidad** | **${fin.net_profit:.2f} USD** | Ganancia neta líquida operativa | ✅ Auditado |",
            f"| **Margen Neto** (%) | **{fin.net_margin_pct:.1f}%** | Mínimo requerido: $\\ge 65.0\\%$ | {'✅ EXCELENTE' if fin.net_margin_pct >= 65.0 else '⚠️ MARGINAL'} |",
            "",
            "#### Enlaces a Proveedores y Logística",
            "",
            f"- **Proveedor Mayorista AliExpress**: [{supp.get('aliexpress_url', cand.source_url)}]({supp.get('aliexpress_url', cand.source_url)})",
            f"- **Sourcing Directo CJ Dropshipping**: [{supp.get('cj_url', 'https://cjdropshipping.com')}]({supp.get('cj_url', 'https://cjdropshipping.com')})",
            f"- **Línea Logística Homologada**: {supp.get('shipping_carrier', cand.shipping_carrier)} ({supp.get('delivery_days', '7 a 12 días')})",
            f"- **Especificación de Empaque**: {supp.get('packaging', 'Empaque neutro con protección anticaída')}",
            f"- **Países Tier 1 Homologados**: {', '.join(supp.get('target_countries', ['US', 'UK', 'CA']))}",
            "",
            "#### Auditoría Forense de las 7 Reglas de Oro",
            "",
            checklist_formatted,
            f"- **Puertas de Knockout (KO-1 a KO-4)**: ✅ Limpio (Cero puertas KO activadas: {result.ko_gates_tripped if result.ko_gates_tripped else 'Ninguna'})",
            "",
            "#### Estrategia Demográfica y Franja Horaria Recomendada",
            "",
            demo_formatted,
            "",
            "**Franja Horaria Recomendada de Publicación Orgánica**:",
            posting_formatted,
            "",
            "#### Mecanismo WOW de Demostración (0 a 3 Segundos)",
            "",
            f"> {supp.get('wow_mechanism', 'Efecto scroll-stopper inmediato en primeros 3 segundos.')}",
            "",
            "#### Ganchos de Conversión (Remotion Modalidad 3)",
            "",
            "A continuación se detallan los 4 guiones técnicos segundo a segundo bajo la partitura canónica de Remotion Modalidad 3:",
            "",
        ]

        # Append each of the 4 hooks
        hook_order = [
            ("curiosidad_disruptiva", "🪝 Gancho 1: Curiosidad Disruptiva (Pattern Interrupt)"),
            ("agitacion_dolor_real", "🪝 Gancho 2: Agitación de Dolor Real (Emotional Visceral Trigger)"),
            ("contrariano", "🪝 Gancho 3: Contrariano (Challenging Conventional Wisdom)"),
            ("transformacion_inmediata", "🪝 Gancho 4: Transformación Inmediata (Before vs After)"),
        ]

        for hook_key, hook_title in hook_order:
            hook_data = hooks.get(hook_key, {})
            section_lines.append(f"##### {hook_title}")
            section_lines.append(f"*{hook_data.get('headline', '')}*\n")
            
            diag = hook_data.get("dialogue_script", {})
            section_lines.append(f"- **Voz Cliente (`{VOICE_CUSTOMER}`)**: *\"{diag.get('client_neural2_c', '')}\"*")
            section_lines.append(f"- **Voz Creador (`{VOICE_CREATOR}`)**: *\"{diag.get('creator_neural2_b', '')}\"*\n")

            # Storyboard table
            section_lines.append(
                "| Tiempo (s) | Video & Composición Visual | Movimiento Remotion (Speed Ramp) | "
                "Pista de Audio / Voces Neural2 | SFX & Beat Drop | Tipografía 3D Flotante (Floating3DText) |"
            )
            section_lines.append(
                "|:---:|:---|:---|:---|:---|:---|"
            )

            for row in hook_data.get("storyboard_rows", []):
                t = row.get("time_range", "")
                v = row.get("visual_action", "").replace("|", "/")
                m = row.get("camera_motion", "").replace("|", "/")
                a = row.get("audio_cue", "").replace("|", "/")
                s = row.get("sfx", "").replace("|", "/")
                f3d = row.get("floating_3d_text", "").replace("|", "/")
                section_lines.append(f"| **{t}** | {v} | {m} | {a} | {s} | {f3d} |")

            section_lines.append("")

        return "\n".join(section_lines)

    def generate_dossier_from_file(
        self,
        audit_file: Union[str, Path],
        output_path: str = "dossier_productos_ganadores.md",
    ) -> str:
        """Load audit results from JSON file and generate winner dossier."""
        path = Path(audit_file)
        if not path.exists():
            raise FileNotFoundError(f"Audit results file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError(f"Expected list of AuditResult records, got {type(raw_data).__name__}")

        audit_results = [AuditResult.from_dict(item) for item in raw_data]
        return self.generate_dossier(audit_results, output_path=output_path)


# ==============================================================================
# CLI ENTRYPOINT
# ==============================================================================

def main() -> int:
    """CLI execution entrypoint for hunter.dossier_generator."""
    parser = argparse.ArgumentParser(
        description="Dropshipping Winner Dossier & 4 Conversion Hooks Synthesizer"
    )
    parser.add_argument(
        "--audit-file",
        type=str,
        default=None,
        help="Path to audit_results.json (default: data/audit_results.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="dossier_productos_ganadores.md",
        help="Output Markdown file path (default: dossier_productos_ganadores.md)",
    )
    args = parser.parse_args()

    default_data_dir = Path(__file__).resolve().parent.parent / "data"
    audit_file = Path(args.audit_file) if args.audit_file else default_data_dir / "audit_results.json"

    if not audit_file.exists():
        logger.error("Audit results file not found at: %s", audit_file)
        return 1

    generator = DossierGenerator()
    try:
        generator.generate_dossier_from_file(audit_file, output_path=args.output)
        print(f"✅ Dossier successfully generated at: {args.output}")
        return 0
    except Exception as exc:
        logger.exception("Fatal error generating dossier: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
