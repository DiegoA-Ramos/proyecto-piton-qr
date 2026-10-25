# 1. Crear un diccionario que relacione cada carácter con su ASCII
TABLA_ASCII = {chr(i): i for i in range(32, 127)}

def validar_texto(texto):
    """Validar que el texto solo contenga caracteres permitidos por el diccionario ASCII"""
    for caracter in texto:
        if caracter not in TABLA_ASCII:
            return False, caracter
    return True, None

def caracter_a_binario(codigo_ascii, bits=8):
    """Convierte un entero ASCII a binario de 8 bits usando desplazamientos"""
    resultado = ""
    for i in range(bits - 1, -1, -1):
        bit = (codigo_ascii >> i) & 1
        resultado += str(bit)
    return resultado

def procesar_etapa2(texto):
    # Validar entrada
    es_valido, char_invalido = validar_texto(texto)
    if not es_valido:
        raise ValueError(f"El carácter '{char_invalido}' no está soportado en la tabla ASCII.")

    # Requerimiento: Convertir texto a ASCII y guardarlo en un VECTOR
    vector_ascii = [TABLA_ASCII[c] for c in texto]

    # Requerimiento: Convertir texto a ASCII y luego unir los números en una sola cadena
    cadena_numerica_ascii = "".join(str(num) for num in vector_ascii)

    # Convertir a cadena de bits binarios (8 bits por carácter)
    vector_binario = [caracter_a_binario(num) for num in vector_ascii]
    datos_binarios = "".join(vector_binario)

    return vector_ascii, cadena_numerica_ascii, datos_binarios

def sacar_longitud(texto):
    longitud = len(texto)
    return longitud

def entero_a_binario(numero, bits):
    """Convierte un entero a binario con ancho fijo de bits"""
    return format(numero, f'0{bits}b')

def construir_etapa3(texto, total_bits=224):
    """Construye el flujo completo de bits para un QR Versión 2 (25x25, nivel M)"""
    MODO = "0100"  # indicador de modo: byte

    longitud = sacar_longitud(texto)
    if longitud > 255:
        raise ValueError("El texto es muy largo para el contador de 8 bits.")
    contador_longitud = entero_a_binario(longitud, 8)

    _, _, datos_binarios = procesar_etapa2(texto)

    bitstream = MODO + contador_longitud + datos_binarios

    espacio_restante = total_bits - len(bitstream)
    if espacio_restante < 0:
        raise ValueError(
            f"El texto no cabe en {total_bits} bits (máx. ~{ (total_bits - 12) // 8 } caracteres)."
        )

    # Terminador: hasta 4 ceros, solo los que alcancen a caber
    terminador = "0" * min(4, espacio_restante)
    bitstream += terminador

    # Completar hasta el siguiente múltiplo de 8
    while len(bitstream) % 8 != 0:
        bitstream += "0"

    # Bytes de relleno alternados (estándar QR)
    bytes_relleno = ["11101100", "00010001"]
    i = 0
    while len(bitstream) < total_bits:
        bitstream += bytes_relleno[i % 2]
        i += 1

    return bitstream[:total_bits], MODO, contador_longitud, datos_binarios, terminador

# ---------------------------------------------------------------
# CORRECCIÓN REED-SOLOMON: QR Versión 2, nivel M (un solo bloque)
# ---------------------------------------------------------------
PALABRAS_DATOS = 28
PALABRAS_CORRECCION = 16
BITS_REMANENTES = 7


def multiplicar_gf256(a, b):
    """Multiplica bytes en GF(256) con el polinomio primitivo QR 0x11D."""
    producto = 0
    while b:
        if b & 1:
            producto ^= a
        b >>= 1
        a <<= 1
        if a & 0x100:
            a ^= 0x11D
    return producto


def generar_palabras_correccion(datos, cantidad=PALABRAS_CORRECCION):
    """Devuelve el resto de dividir datos * x^cantidad entre el generador RS.

    Los coeficientes se ordenan de mayor a menor grado; las raíces del
    generador son alfa^0, ..., alfa^(cantidad-1), con alfa = 2.
    """
    datos = list(datos)
    if not isinstance(cantidad, int) or not 1 <= cantidad <= 255:
        raise ValueError("La cantidad de palabras de corrección debe estar entre 1 y 255.")
    if len(datos) + cantidad > 255:
        raise ValueError("Un bloque Reed-Solomon no puede superar las 255 palabras.")
    if any(not isinstance(valor, int) or not 0 <= valor <= 255 for valor in datos):
        raise ValueError("Cada palabra de datos debe ser un byte entre 0 y 255.")

    # g(x) = (x + alfa^0)(x + alfa^1)...(x + alfa^(cantidad-1)).
    generador = [1]
    raiz = 1
    for _ in range(cantidad):
        siguiente = [0] * (len(generador) + 1)
        for i, coeficiente in enumerate(generador):
            siguiente[i] ^= coeficiente
            siguiente[i + 1] ^= multiplicar_gf256(coeficiente, raiz)
        generador = siguiente
        raiz = multiplicar_gf256(raiz, 2)

    # División polinomial en GF(256): sumar y restar equivale a XOR.
    dividendo = datos + [0] * cantidad
    for i in range(len(datos)):
        factor = dividendo[i]
        if factor:
            for j, coeficiente in enumerate(generador):
                dividendo[i + j] ^= multiplicar_gf256(factor, coeficiente)
    return dividendo[-cantidad:]


def insertar_correccion_errores(bitstream):
    """Añade las 16 palabras RS y 7 bits remanentes a los 224 bits de datos."""
    if len(bitstream) != PALABRAS_DATOS * 8 or any(bit not in "01" for bit in bitstream):
        raise ValueError("Se requieren exactamente 224 bits binarios para un QR versión 2-M.")
    palabras_datos = [int(bitstream[i:i + 8], 2) for i in range(0, len(bitstream), 8)]
    palabras_correccion = generar_palabras_correccion(palabras_datos)
    bits_correccion = "".join(entero_a_binario(valor, 8) for valor in palabras_correccion)
    # Hay un solo bloque en versión 2-M: no se necesita intercalar bloques.
    return bitstream + bits_correccion + "0" * BITS_REMANENTES, palabras_correccion

# ---------------------------------------------------------------
# ETAPA 4: matriz QR e inserción de bits en zigzag
# ---------------------------------------------------------------
TAMANO = 25  # Versión 2 = 25x25 módulos

def crear_matriz():
    matriz = [[None] * TAMANO for _ in range(TAMANO)]
    reservado = [[False] * TAMANO for _ in range(TAMANO)]
    return matriz, reservado

def colocar_finder(matriz, reservado, f0, c0):
    """Finder 7x7 + separador (área de 8x8 reservada)"""
    for r in range(-1, 8):
        for c in range(-1, 8):
            fr, fc = f0 + r, c0 + c
            if 0 <= fr < TAMANO and 0 <= fc < TAMANO:
                reservado[fr][fc] = True
                dentro = 0 <= r <= 6 and 0 <= c <= 6
                oscuro = dentro and (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                matriz[fr][fc] = 1 if oscuro else 0

def colocar_timing(matriz, reservado):
    for i in range(8, TAMANO - 8):
        valor = 1 if i % 2 == 0 else 0
        matriz[6][i] = valor; reservado[6][i] = True
        matriz[i][6] = valor; reservado[i][6] = True

def colocar_alineacion(matriz, reservado, centro=18):
    for r in range(-2, 3):
        for c in range(-2, 3):
            reservado[centro + r][centro + c] = True
            matriz[centro + r][centro + c] = 0 if max(abs(r), abs(c)) == 1 else 1

def reservar_formato(reservado):
    """Reserva las áreas de información de formato (se llenan en la etapa de máscara)"""
    for i in range(9):
        reservado[8][i] = True
        reservado[i][8] = True
    for i in range(TAMANO - 8, TAMANO):
        reservado[8][i] = True
        reservado[i][8] = True

def preparar_matriz():
    matriz, reservado = crear_matriz()
    colocar_finder(matriz, reservado, 0, 0)
    colocar_finder(matriz, reservado, 0, TAMANO - 7)
    colocar_finder(matriz, reservado, TAMANO - 7, 0)
    colocar_timing(matriz, reservado)
    colocar_alineacion(matriz, reservado)
    reservar_formato(reservado)
    matriz[4 * 2 + 9][8] = 1          # módulo oscuro (fila 17, col 8)
    reservado[4 * 2 + 9][8] = True
    return matriz, reservado

def colocar_bits_zigzag(matriz, reservado, bits):
    """Inserta los bits en zigzag. Devuelve cuántos bits se colocaron."""
    columna = TAMANO - 1
    subiendo = True
    idx = 0
    while columna > 0:
        if columna == 6:              # se salta la columna de timing
            columna -= 1
        filas = range(TAMANO - 1, -1, -1) if subiendo else range(TAMANO)
        for fila in filas:
            for c in (columna, columna - 1):   # derecha primero, luego izquierda
                if not reservado[fila][c]:
                    matriz[fila][c] = int(bits[idx]) if idx < len(bits) else 0
                    idx += 1
        subiendo = not subiendo
        columna -= 2
    return idx

def mostrar_matriz(matriz):
    for fila in matriz:
        print("".join("██" if v == 1 else "  " if v == 0 else "··" for v in fila))

# ---------------------------------------------------------------
# ETAPA 5: enmascaramiento (máscara QR)
# ---------------------------------------------------------------
# Fórmulas del estándar: si la condición es True, se invierte el módulo (XOR 1).
# i = fila, j = columna. Se usa la MÁSCARA 0: (i + j) mod 2 == 0
MASCARAS = {
    0: lambda i, j: (i + j) % 2 == 0,
    1: lambda i, j: i % 2 == 0,
    2: lambda i, j: j % 3 == 0,
    3: lambda i, j: (i + j) % 3 == 0,
    4: lambda i, j: (i // 2 + j // 3) % 2 == 0,
    5: lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    6: lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
    7: lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0,
}

def aplicar_mascara(matriz, reservado, num_mascara=0):
    """Invierte SOLO los módulos de datos (no reservados) que cumplan la fórmula.
    Devuelve una copia: la matriz original queda intacta para comparar."""
    formula = MASCARAS[num_mascara]
    resultado = [fila[:] for fila in matriz]
    for i in range(TAMANO):
        for j in range(TAMANO):
            if not reservado[i][j] and formula(i, j):
                resultado[i][j] ^= 1
    return resultado

def verificar_mascara(antes, despues, reservado):
    """Compara antes/después. Devuelve (datos_modificados, funcionales_intactos)."""
    datos_modificados = 0
    funcionales_intactos = True
    for i in range(TAMANO):
        for j in range(TAMANO):
            cambio = antes[i][j] != despues[i][j]
            if reservado[i][j] and cambio:
                funcionales_intactos = False
            if not reservado[i][j] and cambio:
                datos_modificados += 1
    return datos_modificados, funcionales_intactos

def mostrar_diferencias(antes, despues):
    """Marca con ▒▒ los módulos que cambiaron por la máscara."""
    for i in range(TAMANO):
        print("".join("▒▒" if antes[i][j] != despues[i][j]
                      else ("██" if despues[i][j] == 1 else "  ")
                      for j in range(TAMANO)))

def bits_formato(num_mascara, nivel_ec=0b00):
    """15 bits de formato: nivel EC (M = 00) + máscara (3 bits) + BCH(15,5), XOR 101010000010010."""
    datos = (nivel_ec << 3) | num_mascara
    resto = datos << 10
    generador = 0b10100110111
    for k in range(14, 9, -1):
        if resto >> k & 1:
            resto ^= generador << (k - 10)
    return ((datos << 10) | resto) ^ 0b101010000010010

def colocar_formato(matriz, num_mascara=0):
    """Escribe la información de formato en las áreas ya reservadas (no se enmascara)."""
    bits = bits_formato(num_mascara)
    for i in range(15):
        b = (bits >> i) & 1
        # copia vertical (columna 8)
        if i < 6:
            matriz[i][8] = b
        elif i < 8:
            matriz[i + 1][8] = b
        else:
            matriz[TAMANO - 15 + i][8] = b
        # copia horizontal (fila 8)
        if i < 8:
            matriz[8][TAMANO - 1 - i] = b
        elif i == 8:
            matriz[8][7] = b
        else:
            matriz[8][14 - i] = b
    return bits
# main / simulación
if __name__ == "__main__":
    texto = input("Escribe el texto a convertir: ")
    longitud = sacar_longitud(texto)
    print(f"\nlongitud de texto: {longitud}")
    try:
        vector_ascii, cadena_ascii, datos_binarios = procesar_etapa2(texto)

        print("\n--- RESULTADOS ETAPA 2 ---")
        print("1. Texto ingresado:", texto)
        print("2. Vector ASCII:", vector_ascii)
        print("3. Números ASCII en una sola cadena:", cadena_ascii)
        print("4. Datos binarios completos (8 bits):", datos_binarios)

        # AQUÍ FALTABA LA LLAMADA A LA FUNCIÓN
        bitstream, modo, contador, datos, terminador = construir_etapa3(texto)

        print("\n--- RESULTADOS ETAPA 3 ---")
        print("Modo:            ", modo)
        print("Longitud (8bit): ", contador)
        print("Datos ASCII:     ", datos)
        print("Terminador:      ", terminador)
        print("Bitstream final: ", bitstream)
        print("Bits totales:    ", len(bitstream))

        bitstream_completo, palabras_correccion = insertar_correccion_errores(bitstream)
        print("\n--- CORRECCIÓN REED-SOLOMON ---")
        print("Palabras de corrección:", palabras_correccion)
        print("Bitstream con corrección:", bitstream_completo)
        print("Bits totales con corrección:", len(bitstream_completo))

        # ETAPA 4: matriz y zigzag
        matriz, reservado = preparar_matriz()
        total = colocar_bits_zigzag(matriz, reservado, bitstream_completo)
        print("\n--- RESULTADOS ETAPA 4 ---")
        print("Módulos de datos disponibles:", total)  # debe dar 359
        mostrar_matriz(matriz)

        # ETAPA 5: enmascaramiento
        MASCARA = 0
        print("\n--- RESULTADOS ETAPA 5: ENMASCARAMIENTO ---")
        print("Máscara usada:", MASCARA, "-> fórmula: (fila + columna) % 2 == 0")

        matriz_enmascarada = aplicar_mascara(matriz, reservado, MASCARA)

        print("\nANTES del enmascaramiento:")
        mostrar_matriz(matriz)
        print("\nDESPUÉS del enmascaramiento:")
        mostrar_matriz(matriz_enmascarada)
        print("\nDiferencias (▒▒ = módulo invertido por la máscara):")
        mostrar_diferencias(matriz, matriz_enmascarada)

        modificados, intactos = verificar_mascara(matriz, matriz_enmascarada, reservado)
        print("\nMódulos de datos invertidos:", modificados)
        print("Módulos funcionales intactos:", "Sí" if intactos else "NO")

        # Información de formato (EC nivel M + máscara) para que el QR sea legible
        formato = colocar_formato(matriz_enmascarada, MASCARA)
        print("Bits de formato:", format(formato, "015b"))  # M + máscara 0 = 101010000010010

        print("\n--- MATRIZ QR FINAL ---")
        mostrar_matriz(matriz_enmascarada)
    except ValueError as e:
        print(f"\nError de validación: {e}")