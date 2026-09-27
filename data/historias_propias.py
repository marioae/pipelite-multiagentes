"""Entregable 1 del reto — 3 historias clinicas sinteticas propias.

TODOS los nombres, cedulas, direcciones y telefonos son ficticios, inventados
para este ejercicio. No corresponden a personas reales. Los telefonos usan el
rango 555 reservado para ficcion, igual que el dataset de clase.

Criterio de la rubrica cubierto (20%): las 3 historias son propias, tienen los
4 identificadores presentes y mezclados en el texto libre, y una condicion
medica clara y distinta entre si:

    REG-P01  Cardiovascular   — hipertension arterial
    REG-P02  Urologia         — infeccion urinaria
    REG-P03  Endocrinologia   — diabetes mellitus tipo 2
"""

ENCABEZADOS = [
    "ID_Registro",
    "Nombre completo",
    "Cédula",
    "Dirección",
    "Teléfono",
    "Fecha de consulta",
    "Nota clínica (texto libre)",
]

HISTORIAS_PROPIAS = [
    {
        "ID_Registro": "REG-P01",
        "Nombre completo": "Carlos Andrés Mendoza Rojas",
        "Cédula": "12.345.678",
        "Dirección": "Cl 10 #5-20, Santa Cruz de la Sierra",
        "Teléfono": "315-555-0123",
        "Fecha de consulta": "2026-09-26",
        "Nota clínica (texto libre)": (
            "Paciente Carlos Andrés Mendoza Rojas, CC 12.345.678, 45 años, vive en "
            "Cl 10 #5-20, Santa Cruz de la Sierra, tel. 315-555-0123. Consulta por "
            "dolor de cabeza ocasional, mareos y sensación de presión en la cabeza "
            "desde hace aproximadamente 2 semanas. Presión arterial 158/96 mmHg, "
            "frecuencia cardíaca 82 lpm. Padre con antecedente de hipertensión "
            "arterial. Fuma aproximadamente 5 cigarrillos al día. Consume alcohol "
            "ocasionalmente, unas 2 veces al mes."
        ),
    },
    {
        "ID_Registro": "REG-P02",
        "Nombre completo": "María Fernanda Castillo Vargas",
        "Cédula": "1.012.345.678",
        "Dirección": "Av. Los Pinos #245, Cochabamba",
        "Teléfono": "317-555-0456",
        "Fecha de consulta": "2026-09-26",
        "Nota clínica (texto libre)": (
            "Se atiende a María Fernanda Castillo Vargas, 32 años, CC 1.012.345.678, "
            "con domicilio en Av. Los Pinos #245, Cochabamba y teléfono 317-555-0456. "
            "Refiere ardor al orinar, aumento de la frecuencia urinaria y dolor leve "
            "en la parte baja del abdomen desde hace 3 días. Examen general de orina: "
            "leucocitos 25-30 por campo y nitritos positivos. Antecedente de infección "
            "urinaria previa hace aproximadamente 1 año. No fuma. Consume alcohol "
            "ocasionalmente, alrededor de 1 vez al mes."
        ),
    },
    {
        "ID_Registro": "REG-P03",
        "Nombre completo": "José Miguel Paredes Salazar",
        "Cédula": "23.456.789",
        "Dirección": "Cl 8 #12-35, La Paz",
        "Teléfono": "318-555-0789",
        "Fecha de consulta": "2026-09-26",
        "Nota clínica (texto libre)": (
            "José Miguel Paredes Salazar (CC 23.456.789), 58 años, residente en "
            "Cl 8 #12-35, La Paz, contacto 318-555-0789. Acude por aumento de la sed, "
            "mayor frecuencia urinaria y cansancio durante aproximadamente 1 mes. "
            "Glucemia en ayunas 186 mg/dL; HbA1c 8,2 %. Madre con diabetes mellitus "
            "tipo 2. No fuma. Consume alcohol ocasionalmente, 1 a 2 veces al mes."
        ),
    },
]


# Resumen de cada historia para la documentacion (guia de cumplimiento):
# (registro, especialidad, condicion, evidencia en la nota que la sustenta).
RESUMEN_CLINICO = [
    ("REG-P01", "Cardiovascular", "Hipertensión arterial",
     "Presión arterial 158/96 mmHg (una sola toma), cefalea y mareos de 2 semanas"),
    ("REG-P02", "Urología", "Infección urinaria baja",
     "Leucocitos 25-30 por campo y nitritos positivos, con ardor al orinar de 3 días"),
    ("REG-P03", "Endocrinología", "Diabetes mellitus tipo 2",
     "Glucemia en ayunas 186 mg/dL y HbA1c 8,2 %, con sed y poliuria de 1 mes"),
]


def como_filas() -> list[list[str]]:
    """Las 3 historias como filas listas para escribir al .xlsx."""
    return [ENCABEZADOS] + [[h[c] for c in ENCABEZADOS] for h in HISTORIAS_PROPIAS]
