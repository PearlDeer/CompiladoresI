# Proyecto Compiladores - Fase 1 y Fase 2

Proyecto escolar en Python con PyQt6 para analizar codigo fuente mediante dos
fases principales:

1. Analisis lexico.
2. Analisis sintactico descendente recursivo con construccion de AST.

La interfaz grafica no contiene reglas del compilador. Su responsabilidad es
leer el codigo del editor, invocar `compilador.py`, recibir JSON y mostrar
tokens, errores, tabla de simbolos y arbol sintactico.

## Estructura del proyecto

```text
ProyectoCompiladores/
+-- code/
|   +-- scripts/
|       +-- compilador.py
|       +-- compilador_ide.py
|       +-- compiler/
|           +-- __init__.py
|           +-- analisis_lexico.py
|           +-- analisis_sintactico.py
|           +-- ast_node.py
|           +-- errores.py
+-- pruebas/
|   +-- valido_1.txt
|   +-- valido_2.txt
|   +-- con_errores.txt
|   +-- operadores_multilinea.txt
+-- salidas/
|   +-- tokens.txt
|   +-- ast.txt
|   +-- errores_sintacticos.txt
+-- README.md
```

## Archivos principales

`code/scripts/compiler/analisis_lexico.py`

Contiene el analizador lexico. Lee codigo fuente y genera tokens con:

- `tipo`: clasificacion del token.
- `token`: lexema visible.
- `lexema`: copia del lexema para compatibilidad con el parser.
- `linea`: linea donde inicia el token.
- `columna`: columna donde inicia el token.

Tambien genera errores lexicos y tabla de simbolos.

`code/scripts/compiler/analisis_sintactico.py`

Contiene el parser descendente recursivo. Recibe la lista de tokens del lexer,
valida la gramatica, construye el AST y genera errores sintacticos recuperables.

`code/scripts/compiler/ast_node.py`

Define `ASTNode`, la clase simple usada para representar el arbol. Puede
convertirse a diccionario para PyQt6 o a texto indentado para `ast.txt`.

`code/scripts/compiler/errores.py`

Define `ErrorCompilador`, usado para normalizar errores con tipo, descripcion,
linea y columna.

`code/scripts/compilador.py`

Es la fachada del compilador. Ejecuta `lexico` o `sintactico`, guarda archivos
en `salidas/` y regresa JSON para la interfaz.

`code/scripts/compilador_ide.py`

Es la interfaz PyQt6. Muestra:

- Tabla de tokens.
- AST en `QTreeWidget`, como estructura tipo carpetas.
- Tabla de simbolos.
- Errores lexicos.
- Errores sintacticos.

No realiza analisis semantico ni codigo intermedio.

## Flujo visual del IDE

El IDE trabaja con un unico boton de compilacion:

```text
Ejecutar [F5]
```

Al presionarlo se ejecuta automaticamente el flujo completo disponible:

```text
codigo fuente -> analisis lexico -> analisis sintactico -> AST -> errores
```

Ya no existen botones separados para ejecutar solo lexico o solo sintactico en
la barra superior. La razon es evitar confusiones durante la exposicion: una
sola accion analiza el programa completo y actualiza todos los paneles.

Los resultados se distribuyen asi:

- Pestana `Lexico`: muestra todos los tokens generados.
- Pestana `Sintactico`: muestra el AST completo.
- Pestana `Tabla de Simbolos`: muestra los identificadores detectados.
- Panel `Errores Lexicos`: muestra errores de tokenizacion.
- Panel `Errores Sintacticos`: muestra errores de estructura gramatical.

## Visualizacion del AST

El AST se muestra en una sola columna llamada `Arbol Sintactico Abstracto`.
Cada fila incluye la informacion completa del nodo para evitar nombres cortados
o ambiguos.

Formato visual de cada fila:

```text
NombreDelNodo | valor: lexema | tipo: clasificacion
```

Ejemplos:

```text
Programa
ListaDeclaracion
DeclaracionVariable
Tipo | valor: int | tipo: tipo
Identificador | valor: contador | tipo: id
OperacionRelacional | valor: == | tipo: rel_op
Numero | valor: 10 | tipo: NUMERO_ENTERO
```

Si un nodo no tiene valor o tipo, solo se muestra su nombre. Ademas, cada fila
tiene tooltip con la misma etiqueta completa.

## Gramatica implementada

```text
programa -> main { lista_declaracion }
lista_declaracion -> declaracion*
declaracion -> declaracion_variable | sentencia
declaracion_variable -> tipo identificador ;
identificador -> id (, id)*
tipo -> int | float | bool

sentencia -> seleccion
          | iteracion
          | repeticion
          | sent_in
          | sent_out
          | asignacion
          | sent_expresion

asignacion -> id = sent_expresion
sent_expresion -> expresion ; | ;

seleccion -> if expresion then lista_declaracion [else lista_declaracion] end
iteracion -> while expresion lista_declaracion end
repeticion -> do lista_declaracion while expresion

sent_in -> cin >> id ;
sent_out -> cout << salida ;
salida -> cadena
        | expresion
        | cadena << expresion
        | expresion << cadena

expresion -> expresion_simple [rel_op expresion_simple]
rel_op -> < | <= | > | >= | == | !=

expresion_simple -> termino (suma_op termino)*
suma_op -> + | - | ++ | --

termino -> factor (mult_op factor)*
mult_op -> * | / | %

factor -> componente (^ componente)*
pot_op -> ^

componente -> ( expresion )
            | numero
            | id
            | bool
            | op_logico componente

op_logico -> && | || | !
cadena -> "cualquier texto"
```

Nota: la gramatica original tiene recursividad izquierda en producciones como
`lista_declaracion`, `expresion_simple`, `termino` y `factor`. Para poder usar
parser descendente recursivo, se implementaron con ciclos equivalentes.

## Regla especial: operadores dobles con saltos de linea

El lexer acepta operadores dobles aunque sus dos caracteres esten separados por
espacios, saltos de linea, lineas vacias o comentarios.

Ejemplos validos:

```text
a+

+;

if a =

= b then
  cout <

  < "iguales";
else
  cin >

  > a;
end
```

Tokens producidos:

- `+` seguido de `+` se reconoce como `++`.
- `-` seguido de `-` se reconoce como `--`.
- `=` seguido de `=` se reconoce como `==`.
- `<` seguido de `=` se reconoce como `<=`.
- `>` seguido de `=` se reconoce como `>=`.
- `!` seguido de `=` se reconoce como `!=`.
- `&` seguido de `&` se reconoce como `&&`.
- `|` seguido de `|` se reconoce como `||`.
- `<` seguido de `<` se reconoce como `<<`.
- `>` seguido de `>` se reconoce como `>>`.

La linea y columna guardadas para el token combinado corresponden al primer
caracter del operador.

## Funciones del analizador lexico

`crear_token(numero, lexema, tipo, linea, columna)`

Crea el diccionario estandar de token que usan el parser y la interfaz.

`analisis_lexico(codigo)`

Recorre todo el codigo fuente caracter por caracter. Reconoce palabras
reservadas, identificadores, numeros enteros, numeros reales, cadenas,
operadores, simbolos y comentarios. Los comentarios se ignoran como tokens.

`buscar_siguiente_significativo(inicio)`

Busca el siguiente caracter que no sea espacio ni comentario. Esta funcion es
la que permite unir operadores partidos por salto de linea.

`guardar_tokens(tokens, ruta)`

Guarda la lista de tokens en `salidas/tokens.txt`.

## Funciones del parser

`parse`

Punto de entrada del parser. Valida que el programa tenga la forma:

```text
main { lista_declaracion }
```

`lista_declaracion`

Procesa declaraciones y sentencias hasta encontrar un cierre como `}`, `end`,
`else`, `while` o fin de archivo.

`declaracion`

Decide si la entrada actual es una declaracion de variable o una sentencia.

`declaracion_variable`

Valida declaraciones como:

```text
int x, y;
float total;
bool activo;
```

`sentencia`

Selecciona la funcion correcta segun el token actual: `if`, `while`, `do`,
`cin`, `cout`, asignacion o expresion simple como `a++;`.

`asignacion`

Valida:

```text
id = sent_expresion
```

`sent_expresion`

Valida una expresion terminada en punto y coma, o una expresion vacia:

```text
x = 10;
x = ;
```

`seleccion`

Valida condicionales:

```text
if expresion then
  lista_declaracion
else
  lista_declaracion
end
```

`iteracion`

Valida ciclos `while` cerrados con `end`.

`repeticion`

Valida ciclos `do ... while expresion`.

`sent_in`

Valida entrada:

```text
cin >> id;
```

`sent_out` y `salida`

Validan salida:

```text
cout << "texto";
cout << x;
cout << "x" << x;
cout << x << "texto";
```

`expresion`

Valida expresiones relacionales opcionales, por ejemplo `x < 10` o `a == b`.

`expresion_simple`

Valida sumas, restas, incrementos y decrementos. Tambien acepta `++` y `--`
como operadores postfix en expresiones como:

```text
a++;
b--;
```

`termino`

Valida multiplicacion, division y modulo.

`factor`

Valida potencia con `^`.

`componente`

Valida parentesis, numeros, identificadores, booleanos y operadores logicos.

`sincronizar`

Permite recuperacion de errores. Cuando se encuentra una sentencia invalida, el
parser avanza hasta un punto seguro para intentar continuar el analisis.

## Manejo de errores

Cada error contiene:

- Tipo de error.
- Descripcion.
- Linea.
- Columna.

Ejemplo:

```text
Error Sintactico - Linea 5, Columna 11: Se esperaba componente de expresion
```

Los errores sintacticos se muestran en el IDE y se guardan en:

```text
salidas/errores_sintacticos.txt
```

## Salidas generadas

`salidas/tokens.txt`

Lista de tokens generados por el analizador lexico.

`salidas/ast.txt`

AST en formato de texto indentado.

`salidas/errores_sintacticos.txt`

Lista de errores sintacticos. Si no hay errores, escribe:

```text
Sin errores sintacticos.
```

## Pruebas incluidas

`pruebas/valido_1.txt`

Programa valido con declaraciones multiples, asignaciones, booleanos, `if`,
`else`, `cin` y `cout`.

`pruebas/valido_2.txt`

Programa valido con `while`, `do while`, operaciones aritmeticas y salida.

`pruebas/con_errores.txt`

Programa con errores sintacticos para probar recuperacion y reporte de linea y
columna.

`pruebas/operadores_multilinea.txt`

Programa valido para demostrar que operadores como `++`, `--`, `==`, `<<` y
`>>` pueden escribirse con saltos de linea entre sus caracteres.

## Ejecucion por consola

Analisis lexico:

```bash
venv\Scripts\python.exe code\scripts\compilador.py lexico pruebas\valido_1.txt
```

Analisis sintactico:

```bash
venv\Scripts\python.exe code\scripts\compilador.py sintactico pruebas\valido_1.txt
```

Prueba de operadores multilinea:

```bash
venv\Scripts\python.exe code\scripts\compilador.py sintactico pruebas\operadores_multilinea.txt
```

## Relacion con los requisitos de Fase 2

- Lee tokens generados por el analizador lexico.
- Cada token contiene tipo, lexema, linea y columna.
- El parser es descendente recursivo.
- Valida la estructura gramatical del programa.
- Construye un AST.
- Reporta errores sintacticos con tipo, mensaje, linea y columna.
- Intenta continuar el analisis si el error no es fatal.
- El AST se visualiza en PyQt6 con `QTreeWidget`.
- Genera `tokens.txt`, `ast.txt` y `errores_sintacticos.txt`.
- Incluye mas de dos pruebas validas y una prueba con errores.
- Mantiene separada la interfaz grafica del analizador sintactico.
