import os
import io
import shutil

import Constant

import numpy as np

from pathlib import Path


_DATASET = Constant.DATA_FOLDER / "OutlierDetectionDataset"
_RESULT = Constant.RESULTS_FOLDER / "OutlierDetection"
_TEMP_RESULT = Constant.TEMP_RESULT_FOLDER / "OutlierDetection"

###########################################################################################
# PUNTUACION
###########################################################################################

"""
Retorna Pseudo-Inverted Compactness Score (Camacho-Colados) para todos los w en el conjunto C = W + {w}

:param embedding: lista de vectores de palabras
:param W: lista de palabras
:param w: palabra a la cual calcula puntaje respecto a conjunto W
:param phrase: determina si se evaluan frases

:return: puntaje de palabra w respecto a conjunto W
"""
def getPseudoInvertedCompactnessScore(embedding, W, w, phrase):
    sum = 0
    k = 0
    for word in W:
        # TODO: inclusion de frase durante la validacion

        if not word in embedding:
            continue

        if w in embedding:
            sum += (embedding.similarity(word, w) + embedding.similarity(w, word))

        k += 1

    return (sum / k)


"""
Elimina palabras dentro de conjunto principal y conjunto outlier
"""
def omitOOVWord(embedding, main_set, outlier_set):
    res_main_set = []
    res_outlier_set = []
    main_omited = 0
    outlier_omited = 0

    for w in main_set:
        if w in embedding:
            res_main_set.append(w)
        else:
            main_omited += 1

    for w in outlier_set:
        if w in embedding:
            res_outlier_set.append(w)
        else:
            outlier_omited += 1

    return res_main_set, res_outlier_set, main_omited, outlier_omited


"""
Obtencion de puntaje del test para un solo archivo/conjunto

:param embedding: lista de vectores de palabras
:param main_set: conjunto principal de palabras
:param outlier_set: conjunto de palabras outliers
:param phrase: determina si se evaluan frases
:param exist_oov: determina si se solo palabras en la interseccion de vocabularios

:return: valor de OP y OD para cada palabra en outlier_set, respecto a main_set
"""
def getFileScores(embedding, main_set, outlier_set, phrase, exist_oov):
    OP = []
    OD = []
    for outlier in outlier_set:
        # Obtencion de puntaje para outlier (nos importa su posicion respecto al resto de puntajes)
        W = main_set
        p = getPseudoInvertedCompactnessScore(embedding, W, outlier, phrase)
        pos = len(main_set)

        W_outlier = W
        for i in range(len(W_outlier)):

            C = W_outlier[0: i] + W_outlier[i+1:] + [outlier]
            w = W_outlier[i]

            p_i = getPseudoInvertedCompactnessScore(embedding, C, w, phrase)
            if p_i < p:
                pos -= 1

        OP.append(pos)
        OD.append(1 if pos == len(main_set) else 0)

    return OP, OD


"""
Obtencion de accuracy y OPP

:param embedding: lista de vectores de palabras
:param test_sets: lista de pares de conjuntos [main_set, outlier_set]

:return: accuracy y OPP
"""
def getScores(embedding, test_sets, phrase, exist_oov):
    # Suma de valores op y od
    cant_test = 0
    sum_op = 0.0
    sum_od = 0.0

    # Obtencion de porcentaje de omision
    total_main = 0
    total_main_omited = 0
    total_outlier = 0
    total_outlier_omited = 0
    total_omited_sets = 0

    count = 0
    for test in test_sets:
        count += 1
        print(">>> Test " + str(count) + " of " + str(len(test_sets)))
        main_set, outlier_set = test
        total_main += len(main_set)
        total_outlier += len(outlier_set)

        print(">>> Original set:", end='\n    ')
        print(main_set, end='\n    ')
        print(outlier_set)

        # Determinar cuales palabras de cada set se encuentran en el vocabulario
        if exist_oov:
            main_set, outlier_set, main_omited, outlier_omited = omitOOVWord(embedding, main_set, outlier_set)
            total_main_omited += main_omited
            total_outlier_omited += outlier_omited

            print(">>> In-vocabulary set:", end='\n    ')
            print(main_set, end='\n    ')
            print(outlier_set)

        if len(main_set) < 2 or len(outlier_set) < 1:
            total_omited_sets += 1
            print("Test set invalido, conjunto principal muy pequeño o conjunto outlier vacio\n")
            continue

        OP_list, OD_list = getFileScores(embedding, main_set, outlier_set, phrase, exist_oov)

        print("OP and OD list:")
        print(OP_list)
        print(OD_list)

        temp_sum_op = 0.0
        temp_sum_od = 0.0
        for op in OP_list:
            temp_sum_op += op

        sum_op += (temp_sum_op / len(main_set))

        for od in OD_list:
            temp_sum_od += od

        sum_od += temp_sum_od

        cant_test += len(outlier_set)

    results = []

    if cant_test == 0:
        results = ["Nan", "Nan"]
    else:
        results = [
            (sum_op / cant_test),
            (sum_od / cant_test),
            (total_main_omited * 1.0 / total_main),
            (total_outlier_omited * 1.0 / total_outlier),
            total_omited_sets
        ]

    return results


###########################################################################################
# MANEJO DE ARCHIVOS
###########################################################################################

"""
Obtencion de la lista de archivos test

:return: nombre de archivos con test de outlier detection
:type: list
"""
def getTestFiles():
    if not _DATASET.exists():
        raise Exception("No se logro encontrar carpeta con test")

    return os.listdir(_DATASET)


"""
Obtencion de las palabras desde el archivo de test, palabras del conjunto y conunto outlier

:param file_name: nombre de archivo con test

:return: par de conjuntos, conjunto principal y conjunto outlier
:type: list
"""
def getWords(file_name, lower):
    main_set = []
    outlier_set = []

    with io.open(_DATASET / file_name, 'r', encoding='utf-8') as f:
        for line in f:
            if line == "\n":
                main_set = outlier_set
                outlier_set = []
                continue

            line = line.strip()
            if lower:
                line = line.lower()

            outlier_set.append(line)

    return main_set, outlier_set


def getTests(lower, cant=-1):
    file_list = getTestFiles()
    test_list = []
    count = 0

    for file in file_list:
        test_list.append(getWords(file, lower))
        count += 1
        if cant <= count and cant > 0:
            break

    return test_list


###########################################################################################
# GUARDAR RESULTADOS
###########################################################################################

"""
Guardado de resultados del test por outlier detection

:param embedding_name: nombre de embedding evaluado
:param results: lista de los resultados (accuraccy, OPP) y datos (% oov outlier, % ovv main set, % grupos omitidos)
                de un embedding, la lista se compone de pares [nombre_resultado, valor_resultado]
:param phrase: determina si se utilizan frases en set de pruebas
:param exist_oov: determina si se consideran palabras fuera del vocabulario
"""
def saveResults(embedding_name, results, phrase, exist_oov):
    extension = ""
    if phrase:
        extension += "_phrase"

    if not exist_oov:
        extension += "_vocabIntersect"

    save_path = _RESULT
    if not save_path.exists():
        os.makedirs(save_path)

    save_path = _RESULT / (embedding_name + extension + ".txt")

    with io.open(save_path, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(r[0] + " " + str(r[1]) + "\n")


###########################################################################################
# EVALUACION POR OUTLIER DETECTION
###########################################################################################

"""
Realizacion de outlier detection test

:param embedding: lista de vectores de palabras
:param embedding_name: nombre del embedding a evaluar
:param phrase: determina si se utilizan frases en set de pruebas
:param existe_ovv: determina si se consideran palabras fuera del vocabulario
"""
def outlierDetectionTest(embedding, embedding_name, phrase=False, exist_oov=True, lower=True):
    # Obtencion de conjuntos, principal y outlier
    test_list = getTests(lower)

    # TODO: adicion de datos (%oov outlier, %oov main set, %grupos omitidos)
    results = getScores(embedding, test_list, phrase, exist_oov)
    results = [
        ["accuraccy", results[0]],
        ["OPP", results[1]],
        ["%_main_omited", results[2]],
        ["%_outlier_omited", results[3]],
        ["sets_omited", results[4]]
    ]

    print(">>> Resultados:\n    ", end='')
    print(results, end='\n\n')

    saveResults(embedding_name, results, phrase, exist_oov)

