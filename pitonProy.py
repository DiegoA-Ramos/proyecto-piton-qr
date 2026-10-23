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

    except ValueError as e:
        print(f"\nError de validación: {e}")