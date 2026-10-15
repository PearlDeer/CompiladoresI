# Proyecto Compiladores - Fases 1, 2 y 3

Proyecto escolar en Python con PyQt6 para analizar codigo fuente mediante tres
fases principales:

1. Analisis lexico.
2. Analisis sintactico descendente recursivo con construccion de AST.
3. Analisis semantico, AST anotado, tabla de simbolos y verificacion de tipos.

La interfaz grafica no contiene reglas del compilador. Su responsabilidad es
leer el codigo del editor, invocar `compilador.py`, recibir JSON y mostrar
tokens, errores independientes por fase, tabla semantica y ambos arboles.

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
|           +-- analisis_semantico.py
|           +-- ast_node.py
|           +-- errores.py
+-- pruebas/
|   +-- valido_1.txt
|   +-- valido_2.txt
|   +-- con_errores.txt
|   +-- operadores_multilinea.txt
|   +-- semantico_valido.txt
|   +-- semantico_errores.txt
|   +-- test_analisis_semantico.py
|   +-- test_integracion_fase3.py
|   +-- test_ide_fase3.py
|   +-- validar_fase3.py
+-- salidas/
|   +-- tokens.txt
|   +-- ast.txt
|   +-- errores_sintacticos.txt
|   +-- ast_semantico.txt
|   +-- tabla_simbolos.txt
|   +-- errores_semanticos.txt
|   +-- conversiones.txt
|   +-- traza_semantica.txt
|   +-- resultado.json
|   +-- pruebas/
|   +-- evidencias/
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

Tambien genera errores lexicos y un inventario de identificadores con tipo
desconocido. Este inventario no sustituye la tabla semantica.

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

Es la fachada del compilador. Ejecuta `lexico`, `sintactico` o `semantico`, guarda archivos
en `salidas/` y regresa JSON para la interfaz.

`code/scripts/compilador_ide.py`

Es la interfaz PyQt6. Muestra:

- Tabla de tokens.
- AST en `QTreeWidget`, como estructura tipo carpetas.
- AST semantico y comparacion simultanea con el AST original.
- Tabla de simbolos semantica.
- Errores lexicos.
- Errores sintacticos.
- Errores semanticos.

Delega las tres fases al compilador externo. No ejecuta el programa fuente ni
genera codigo intermedio.

## Flujo visual del IDE

El IDE trabaja con un unico boton de compilacion:

```text
Ejecutar [F5]
```

Al presionarlo se ejecuta automaticamente el flujo completo disponible:

```text
codigo fuente -> lexer -> parser -> AST original -> semantico -> AST anotado
```

Ya no existen botones separados para ejecutar solo lexico o solo sintactico en
la barra superior. La razon es evitar confusiones durante la exposicion: una
sola accion analiza el programa completo y actualiza todos los paneles.

Los resultados se distribuyen asi:

- Pestana `Lexico`: muestra todos los tokens generados.
- Pestana `Sintactico`: muestra el AST completo.
- Pestana `AST Semantico`: muestra tipos, valores calculados, conversiones y ubicaciones.
- Pestana `Comparar AST`: muestra ambos arboles y sincroniza la seleccion.
- Pestana `Tabla de Simbolos`: muestra los identificadores declarados y sus tipos reales.
- Panel `Errores Lexicos`: muestra errores de tokenizacion.
- Panel `Errores Sintacticos`: muestra errores de estructura gramatical.
- Panel `Errores Semanticos`: muestra errores de declaraciones, tipos y condiciones.
- Panel `Resultados`: muestra estado, cantidades, conversiones y fallos de ejecucion.

F5 utiliza `QProcess` y un limite de 30 segundos; el editor permanece disponible.
Si se edita el codigo, los resultados anteriores se identifican como tales.

## Visualizacion del AST

El AST se muestra en una sola columna llamada `Arbol Sintactico Abstracto`.
Las columnas se pueden redimensionar para inspeccionar etiquetas extensas.
Las pestanas de resultados no muestran recuadros emergentes al pasar el cursor.
El AST original puede mostrar el resultado booleano asociado desde su copia
semantica, sin alterar los datos del arbol original.

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

Si un nodo no tiene valor o tipo, solo se muestra su nombre. Los atributos
completos permanecen disponibles en el JSON y en el archivo del AST anotado.

## Gramatica implementada

```text
programa -> main { lista_declaracion }
lista_declaracion -> declaracion*
declaracion -> declaracion_variable | sentencia
declaracion_variable -> tipo identificador ;
identificador -> id [= expresion] (, id [= expresion])*
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
repeticion -> do lista_declaracion while expresion ;

sent_in -> cin >> id ;
sent_out -> cout << salida ;
salida -> cadena
        | expresion
        | cadena << expresion
        | expresion << cadena

expresion -> expresion_logica_or
expresion_logica_or -> expresion_logica_and (|| expresion_logica_and)*
expresion_logica_and -> expresion_relacional (&& expresion_relacional)*
expresion_relacional -> expresion_simple [rel_op expresion_simple]
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

op_logico -> !
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

Valida ciclos `do ... while expresion ;`. El terminador permite distinguir el
cierre del `do` de un `while` anidado. La version inicial aceptaba el terminador
opcional; la implementacion actual lo exige. Se corrigio exclusivamente el
terminador de `pruebas/valido_2.txt`, conservando las reglas del parser.

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

Valida expresiones logicas y relacionales con precedencia `||`, `&&`, relacionales,
suma, multiplicacion, potencia y componentes. Por ejemplo: `x < 10 && !activo`.

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

## Fase 3: analisis semantico

`code/scripts/compiler/analisis_semantico.py` recibe el AST del parser y crea una
copia profunda. Recorre las declaraciones y sentencias, construye la tabla real,
consulta cada uso de identificador, verifica tipos y agrega atributos a la copia.
El AST original conserva sus lexemas, clasificaciones, estructura y ubicaciones.
El modulo no escribe archivos; la fachada realiza la persistencia.

### Atributos y anotaciones

`ASTNode` conserva los cuatro argumentos originales: `nodo`, `valor`, `tipo` e
`hijos`. Se agregaron `linea`, `columna` y `atributos`. `tipo` sigue siendo una
clasificacion sintactica; no se reemplaza por el tipo de dato calculado.

| Atributo | Procedencia y significado |
| --- | --- |
| `tipo_declarado` | Heredado: el tipo de una declaracion se propaga a sus identificadores. |
| `ambito` | Heredado desde el contexto; actualmente `global` en `main`. |
| `tipo_calculado` | Sintetizado desde literales, consultas y operandos. |
| `es_constante`, `valor_constante` | Valor conocido en el punto analizado, incluyendo propagacion de asignaciones previas. |
| `resultado_condicion`, `condicion_valida` | Booleano calculado, desconocido o condicion no evaluable por errores. |
| `contexto_valor` | Identifica la entrada del while o la primera evaluacion del do-while. |
| `conversion_aplicada`, `tipo_contextual` | Promocion `int -> float` exigida por el operador o destino. |
| `direccion`, `desplazamiento` | Celda logica asignada por la tabla a una declaracion. |
| `referencia_tabla_simbolos` | ID del registro utilizado por el nodo identificador. |
| `inicializado_al_usar` | Estado de asignacion conocido en ese punto del recorrido. |
| `id_nodo` | Ruta estructural estable para relacionar ambos arboles y la traza. |

La traza registra herencia, sintesis, inserciones, busquedas, comprobaciones y
conversiones. Cada evento tiene paso, regla, accion, nodo y ubicacion. Las
conversiones conservan el tipo original del operando y anotan su tipo contextual;
no introducen nodos que dificulten la comparacion estructural.

Los valores conocidos de asignaciones compatibles se conservan y propagan:
`y = 5 + 2 - 1` calcula `6`, y luego `y = y + 9` calcula `15`. Se anotan el
identificador, los operandos, la expresion y la asignacion. Un `cin` vuelve
desconocido el valor recibido; una asignacion invalida no sustituye el valor
anterior. Los incrementos/decrementos actualizan el valor conocido y las
expresiones postfix conservan su resultado previo al cambio.

Cuando una condicion es conocida se conserva el estado de la rama seleccionada,
aunque ambas ramas se revisan para detectar errores. Si es desconocida, solo se
conservan los valores iguales en ambas ramas. En `&&` y `||` se respeta el
cortocircuito para no aplicar efectos de operandos omitidos.

Los bucles no se ejecutan hasta terminar: se muestran los valores de su primera
evaluacion, identificados como `entrada` o `1a iter.`. Al salir del analisis de un
bucle que puede repetirse, los valores de variables escritas se vuelven
desconocidos. Un `while` inicialmente falso conserva el estado anterior; un
`do-while` cuya primera condicion es falsa conserva el estado de esa unica
iteracion. `es_constante` en estos nodos significa calculable en el contexto
indicado, no un valor inmutable en todas las vueltas.

La columna `Valor calculado` muestra `true`/`false` cuando la condicion se puede
calcular y `desconocido` cuando faltan valores. Si la condicion es invalida,
muestra `no evaluable`. Por ejemplo, `a > b` no tiene un resultado calculable
si `b` aun no tiene valor; no se asume que vale cero. `valor_inicial_constante`
conserva el inicializador, mientras `valor_conocido`/`valor_actual` describen el
estado actual del recorrido.

### Tabla de simbolos

`TablaSimbolos` es un diccionario por `(ambito, nombre)`. Ofrece `insertar`,
`buscar`, `obtener_tipo`, `detectar_duplicado` y `registrar_uso`. El analizador
inserta exclusivamente declaraciones; no inventa registros para nombres ausentes.
Una declaracion duplicada no reemplaza el tipo ni la direccion de la primera.

Cada registro contiene ID, nombre/lexema, tipo, linea y columna inicial, todas las
lineas, ocurrencias con columna y contexto, ambito, direccion/desplazamiento,
indicadores `declarado`/`inicializado`, el inicializador y el valor conocido actual.
`lineas` contiene una entrada por aparicion: `y = y + 9` registra la misma linea
dos veces. `lineas_unicas` conserva la vista sin repeticiones; `ocurrencias`
distingue cada aparicion por columna y contexto. Sigue existiendo un solo
registro por identificador y ambito.
Las direcciones son celdas logicas consecutivas `0, 1, 2...`; no son bytes de una
maquina o direcciones reales de ejecucion.

Se conserva un solo ambito global en `main`, incluso para declaraciones dentro
de estructuras de control. La visibilidad empieza en la declaracion: usar un
nombre antes de declararlo produce error. No se agregaron funciones ni ambitos
locales que la implementacion anterior no definia.

El indicador de inicializacion realiza un seguimiento conservador: `cin` y
asignaciones compatibles lo activan; un `if` desconocido combina ambas ramas;
un `while` puede ejecutar cero veces; un `do-while` ejecuta su cuerpo una vez.
No se diagnostican lecturas de variables declaradas pero no inicializadas.

### Reglas semanticas y conversiones

| Construccion | Regla implementada |
| --- | --- |
| Declaracion e inicializacion | Propagar tipo, detectar duplicados, insertar y validar inicializador. |
| Asignacion | Tipos iguales o promocion de entero hacia destino flotante. |
| `+`, `-`, `*`, `/`, `^` | Operandos numericos; dos `int` producen `int`; si interviene `float`, resultado `float`. |
| Division entera | Trunca hacia cero; no usa division flotante intermedia. |
| `%` | Exclusivamente entre enteros; resto coherente con division truncada. |
| `^` | Potencia, conservando la asociacion por la izquierda del parser. |
| `++`, `--` | Postfix sobre identificador numerico modificable; forma binaria rechazada semanticamente. |
| `<`, `<=`, `>`, `>=` | Numeros compatibles; resultado `bool`. |
| `==`, `!=` | Numeros compatibles o dos booleanos; resultado `bool`. |
| `&&`, `||`, `!` | Exclusivamente booleanos; resultado `bool`. |
| `if`, `while`, `do-while` | Condicion de tipo `bool`. |
| `cin` | Identificador declarado; valor de ejecucion desconocido. |
| `cout` | Cadena o expresion valida en las formas ya admitidas por el parser. |

`int -> float` se anota en operandos mixtos, comparaciones numericas mixtas e
inicializaciones/asignaciones hacia `float`. Se rechaza `float -> int`, incluso
para un literal como `2.0`. No existen conversiones implicitas entre booleanos y
numeros. `x = ;` es reconocido por la sintaxis existente y rechazado por Fase 3.

### Diagnosticos

| Codigo | Situacion |
| --- | --- |
| `SEM_NO_DECLARADO` | Uso de identificador ausente. |
| `SEM_DUPLICADO` | Declaracion repetida en el mismo ambito. |
| `SEM_TIPOS_INCOMPATIBLES` | Operandos incompatibles en una comparacion. |
| `SEM_CONVERSION_INVALIDA` | Asignacion que exigiria `float -> int`. |
| `SEM_OPERADOR_INVALIDO` | Operador utilizado con tipos o operandos incorrectos. |
| `SEM_ASIGNACION_INCOMPATIBLE` | Tipos incompatibles entre destino y expresion. |
| `SEM_CONDICION_NO_BOOLEANA` | Condicion de control que no es `bool`. |
| `SEM_EXPRESION_VACIA` | Asignacion sin expresion. |
| `SEM_DIVISION_CERO` | Division/resto con divisor constante cero. |
| `SEM_DOMINIO_CONSTANTE` | Operacion constante fuera del dominio permitido. |

Cada error conserva linea, columna, tipo y descripcion. El tipo interno `error`
se propaga para evitar diagnosticos derivados repetidos. El recorrido continua
por otras construcciones. Los errores de proceso/archivos son tecnicos y se
muestran en `Resultados`, sin mezclarse con las tablas de errores del lenguaje.

### Bloqueos y AST parcial

Los errores lexicos bloquean parser y semantico. Los errores sintacticos fatales,
declaraciones incompletas, terminadores ausentes y fallos de bloques bloquean la
fase semantica; el AST sintactico recuperado sigue disponible para inspeccion.

La fachada permite un recorrido parcial solo si todos los errores sintacticos
son componentes de expresion ausentes o cierres de parentesis recuperados y
existe un `ErrorComponente` que conserva el hueco. Este nodo obtiene tipo `error`.
No se permite esta recuperacion ante otros diagnosticos estructurales.
`testlexico.txt`, con `while(x==4 &&);`, cumple esta politica: produce resultados
provisionales, estado `parcial` y `valido=false`. Se conserva el archivo historico
sin reemplazarlo ni corregir su condicion deliberadamente en estas evidencias.

### JSON y archivos de salida

Las tres fases devuelven `tokens`, `errores_lexicos`, `errores_sintacticos`,
`errores_semanticos`, `errores_ejecucion`, `arbol`, `arbol_semantico`,
`tabla_simbolos`, `conversiones`, `traza_semantica`, `estado`, `estado_semantico`
y `valido`. `errores` se conserva como lista agregada para compatibilidad.
En `semantico`, `tabla_simbolos` siempre es la tabla real; si se bloquea, esta
vacia. `tabla_simbolos_lexica` conserva el inventario separado. En las fases
anteriores se mantiene el inventario como `tabla_simbolos` por compatibilidad.

Cada ejecucion actualiza `tokens.txt`, `ast.txt`, `ast_semantico.txt`,
`tabla_simbolos.txt`, `errores_lexicos.txt`, `errores_sintacticos.txt`,
`errores_semanticos.txt`, `errores_ejecucion.txt`, `conversiones.txt`,
`traza_semantica.txt` y `resultado.json`. Las salidas no ejecutadas se limpian o
indican su bloqueo; nunca conservan el arbol semantico de una ejecucion anterior.
Los resultados parciales y bloqueados se identifican en el JSON y el IDE.

### Ejecucion y validacion

Desde la raiz `CompiladoresI`, con el entorno Python/PyQt6 existente:

```powershell
venv\Scripts\python.exe -B code\scripts\compilador.py lexico pruebas\valido_1.txt
venv\Scripts\python.exe -B code\scripts\compilador.py sintactico pruebas\valido_1.txt
venv\Scripts\python.exe -B code\scripts\compilador.py semantico testlexico.txt
venv\Scripts\python.exe -B code\scripts\compilador.py semantico pruebas\semantico_valido.txt salidas\respuesta.json
venv\Scripts\python.exe -B code\scripts\compilador_ide.py
venv\Scripts\python.exe -B -m unittest discover -s pruebas -v
venv\Scripts\python.exe -B pruebas\validar_fase3.py --capturas
```

La CLI acepta `--salidas <directorio>` para aislar evidencias y ejecuciones
simultaneas. Sin esa opcion usa `salidas` del proyecto, independientemente del
directorio actual. La salida opcional es JSON; sin ella, se imprime a stdout.
Codigo de salida `0` significa analisis realizado: revisar `valido` y las listas
para diagnosticos del lenguaje. Los fallos tecnicos retornan `1`; argumentos
invalidos, `2`.

### Casos y evidencias

| Archivo | Resultado de la fase semantica |
| --- | --- |
| `pruebas/valido_1.txt` | Valido, cuatro simbolos y dos conversiones. |
| `pruebas/valido_2.txt` | Valido tras corregir el terminador, dos simbolos y tres conversiones. |
| `pruebas/operadores_multilinea.txt` | Valido, dos simbolos. |
| `pruebas/con_errores.txt` | Trece errores sintacticos; semantico bloqueado. |
| `testlexico.txt` | Dos errores sintacticos, ocho semanticos, seis simbolos y cinco conversiones; parcial. |
| `pruebas/semantico_valido.txt` | Valido; declaraciones inicializadas, conversiones, condiciones y entrada/salida. |
| `pruebas/semantico_errores.txt` | Once errores semanticos que cubren las siete categorias minimas; una conversion valida. |

La suite incluye pruebas del nucleo, integracion CLI/IDE y propagacion de valores.
`test_valores_y_bucles.py` comprueba valores previos, ramas, entradas,
cortocircuito y 51 combinaciones de operadores en estructuras de control.
`validar_fase3.py` ejecuta las tres fases sobre las nueve entradas: 27 casos.
Guarda cada caso en `salidas/pruebas/<nombre>/<fase>/`, un resumen TXT/JSON y
verifica que el archivo historico no cambie. Deja las salidas principales de la
raiz asociadas al analisis de `testlexico.txt`, identificado en el resumen.

Con `--capturas` genera diez PNG en `salidas/evidencias`: AST anotado valido,
comparacion de arboles, tabla del archivo historico, propagacion hasta `y=15`,
condicion historica desconocida, errores semanticos, una vista compacta y tres
vistas del programa maestro (comparador verdadero, bucle falso y motivo desconocido).
Son capturas de widgets reales con el compilador externo, usando
Qt `offscreen`; se registran las fuentes locales de Windows para renderizar
texto legible. `capturas.json` registra fuente, dimensiones y modo de captura.

### Resultados booleanos y pruebas maestras

Las comparaciones, operadores logicos y expresiones bool del AST anotado incluyen
`resultado_booleano`: `true`, `false` o `null` si no puede determinarse. Las
estructuras `Seleccion`, `IteracionWhile` y `RepeticionDoWhile` reciben tambien
ese resultado, ademas de `resultado_condicion` y `condicion_valida`. Los nodos
de operadores registran `operandos_evaluados` (tipo, valor, conocido y motivo).
La traza incluye pasos `evaluacion_booleana` con resultado y motivo.

El IDE muestra los resultados tanto en el AST original como en el anotado y
la comparacion, sin alterar el AST original. La columna visible `Detalle de
evaluacion` muestra operandos conocidos o explica el valor desconocido, sin
recuadros emergentes. Por ejemplo, con `a=55.0` y `b` sin inicializar, `a>b`
no es falso: es desconocido, con detalle `b sin inicializar`. Con `b=10.0`
es `true`; con `b=100.0` es `false`. Tampoco se inventan valores para `cin`,
ramas divergentes o variables modificadas por bucles. Los valores de while
corresponden a su entrada y los de do-while a su primera condicion, despues
del cuerpo; no representan una ejecucion completa del programa.

`Valor calculado` muestra solo el valor, sin sufijos como `(entrada)` o
`(1a iter.)`. Para nodos booleanos, `Detalle de evaluacion` muestra explicitamente
`true` o `false`, incluso en el grupo y la estructura de control que los contiene.
Si no puede determinarse, muestra `desconocido: <motivo>`; una condicion de tipo
invalido muestra `no evaluable: <motivo>`. Los operandos se conservan en sus
nodos hijos y en `operandos_evaluados` del JSON.

- `pruebas/maestro_condiciones_original.txt`: codigo completo compartido, con
  `while(x==4 && y!=9);`. Sin errores lexicos ni sintacticos; ocho errores
  semanticos (identificadores no declarados y conversiones float a int).
- `pruebas/maestro_condiciones_valido.txt`: copia adaptada sin esos errores.
  Declara `suma` y `mas`, inicializa `b` y `c`, usa asignaciones enteras para
  `x`/`y` y dirige `b+3` a `a` float. Fija `x=6` antes del primer do para
  demostrar su condicion falsa; decrementa x en el ultimo while y fija x=1
  antes de la ultima condicion. Conserva todas las estructuras del ejemplo.
- `pruebas/test_condiciones_maestras.py`: prueba ambos programas completos y
  varia inicializaciones, comparadores, &&, ||, !, entradas, tipos invalidos y
  operandos faltantes. Algunas variantes son exclusivamente pruebas estaticas;
  una condicion siempre verdadera no implica que su bucle termine en ejecucion.

```powershell
venv\Scripts\python.exe -B code\scripts\compilador.py semantico pruebas\maestro_condiciones_valido.txt --salidas salidas\maestro
venv\Scripts\python.exe -B -m unittest discover -s pruebas -p test_condiciones_maestras.py -v
```

El archivo historico `testlexico.txt` no se reemplaza.

### Limitaciones conocidas

- Analisis estatico; no ejecuta el codigo ni obtiene valores de entrada.
- Ambito global unico y desplazamientos logicos, sin distribucion fisica en bytes.
- La propagacion de valores e inicializacion es conservadora; no agrega errores de lectura sin inicializar.
- Los valores de bucles corresponden a su evaluacion inicial, no al resultado de ejecutar todas sus vueltas.
- El recorrido de AST parcial es provisional y se limita a la politica documentada.
- El calculo de potencias constantes tiene limites de recursos; el tipo sigue calculandose cuando se omite el valor.
- Se conserva la gramatica previa, incluyendo sus formas limitadas de `cin`/`cout` y asociatividad de potencia.
- Las capturas automatizadas no sustituyen una revision visual interactiva en el escritorio.
