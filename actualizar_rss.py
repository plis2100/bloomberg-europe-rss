from __future__ import annotations

import copy
import email.utils
import html
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser


SALIDA = Path("rss.xml")

MAXIMO_GUARDADOS = 2000


# Canales RSS oficiales de Bloomberg.
FUENTES_BLOOMBERG = {
    "Bloomberg Markets": (
        "https://feeds.bloomberg.com/"
        "markets/news.rss"
    ),
    "Bloomberg Industries": (
        "https://feeds.bloomberg.com/"
        "industries/news.rss"
    ),
    "Bloomberg Technology": (
        "https://feeds.bloomberg.com/"
        "technology/news.rss"
    ),
    "Bloomberg Economics": (
        "https://feeds.bloomberg.com/"
        "economics/news.rss"
    ),
    "Bloomberg Politics": (
        "https://feeds.bloomberg.com/"
        "politics/news.rss"
    ),
}


BME_API = (
    "https://apiweb.bolsasymercados.es/"
    "Market/v1/EQ/ListedCompanies"
)


MERCADOS_BME = {
    "Mercado Continuo": {
        "tradingSystem": "SIBE",
        "mtfSegment": "",
    },
    "BME Growth": {
        "tradingSystem": "MTF",
        "mtfSegment": "BMEGrowth",
    },
    "BME Scaleup": {
        "tradingSystem": "MTF",
        "mtfSegment": "BMEScaleup",
    },
}


# Alias adicionales para compañías que Bloomberg
# puede mencionar por una marca, filial o producto.
ALIAS_ADICIONALES = {
    "ACCIONA": (
        "acciona",
    ),
    "ACCIONA ENERGÍA": (
        "acciona energia",
        "acciona energía",
        "acciona energy",
    ),
    "ACERINOX": (
        "acerinox",
        "north american stainless",
        "vdm metals",
        "columbus stainless",
    ),
    "ACS": (
        "acs group",
        "actividades de construccion y servicios",
        "actividades de construcción y servicios",
        "hochtief",
        "turner construction",
        "cimic",
    ),
    "AENA": (
        "aena",
    ),
    "AIRBUS": (
        "airbus",
    ),
    "ALMIRALL": (
        "almirall",
        "ilumetri",
        "ebglyss",
        "klisyri",
        "skilarence",
    ),
    "AMADEUS": (
        "amadeus it group",
        "amadeus travel",
    ),
    "ARCELORMITTAL": (
        "arcelormittal",
    ),
    "BANCO SABADELL": (
        "banco sabadell",
        "sabadell bank",
        "tsb banking",
    ),
    "BANCO SANTANDER": (
        "banco santander",
        "santander bank",
        "santander group",
        "santander uk",
        "openbank",
    ),
    "BANKINTER": (
        "bankinter",
    ),
    "BBVA": (
        "bbva",
        "banco bilbao vizcaya",
    ),
    "CAIXABANK": (
        "caixabank",
        "caixa bank",
        "bpi bank",
        "banco bpi",
    ),
    "CAF": (
        "construcciones y auxiliar de ferrocarriles",
        "caf rail",
        "caf group",
        "solaris bus",
    ),
    "CELLNEX": (
        "cellnex",
        "cellnex telecom",
    ),
    "CIE AUTOMOTIVE": (
        "cie automotive",
    ),
    "COLONIAL": (
        "inmobiliaria colonial",
        "colonial socimi",
    ),
    "COX": (
        "cox abengoa",
        "cox energy",
        "cox group",
    ),
    "EDREAMS ODIGEO": (
        "edreams odigeo",
        "edreams",
        "opodo",
    ),
    "EIDF": (
        "eidf solar",
        "energia innovacion y desarrollo fotovoltaico",
        "energía innovación y desarrollo fotovoltaico",
    ),
    "ELECNOR": (
        "elecnor",
        "enerfin",
    ),
    "ENAGÁS": (
        "enagas",
        "enagás",
    ),
    "ENDESA": (
        "endesa",
    ),
    "FCC": (
        "fcc group",
        "fomento de construcciones y contratas",
        "fcc environmental",
        "cementos portland valderrivas",
    ),
    "FERROVIAL": (
        "ferrovial",
        "cintra",
    ),
    "FLUIDRA": (
        "fluidra",
        "zodiac pool",
    ),
    "GRIFOLS": (
        "grifols",
        "biotest",
        "haema",
        "plasmacare",
        "bpl plasma",
        "interstate blood bank",
    ),
    "HBX GROUP": (
        "hbx group",
        "hotelbeds",
    ),
    "IAG": (
        "international airlines group",
        "international consolidated airlines",
        "british airways",
        "iberia airlines",
        "aer lingus",
        "vueling",
    ),
    "IBERDROLA": (
        "iberdrola",
        "avangrid",
        "scottishpower",
        "scottish power",
    ),
    "INDITEX": (
        "inditex",
        "zara",
        "bershka",
        "pull&bear",
        "pull and bear",
        "massimo dutti",
        "stradivarius",
        "oysho",
    ),
    "INDRA": (
        "indra sistemas",
        "indra group",
        "minsait",
    ),
    "LLEIDA.NET": (
        "lleida.net",
        "lleidanet",
    ),
    "LOGISTA": (
        "logista group",
        "compania de distribucion integral logista",
        "compañía de distribución integral logista",
    ),
    "MAPFRE": (
        "mapfre",
    ),
    "MELIÁ HOTELS": (
        "melia hotels",
        "meliá hotels",
        "melia hotel",
        "meliá hotel",
    ),
    "MERLIN PROPERTIES": (
        "merlin properties",
    ),
    "METROVACESA": (
        "metrovacesa",
    ),
    "MFE-MEDIAFOREUROPE": (
        "mediaforeurope",
        "mfe-mediaforeurope",
        "mediaset españa",
        "mediaset espana",
    ),
    "NATURGY": (
        "naturgy",
        "gas natural fenosa",
    ),
    "NEINOR HOMES": (
        "neinor homes",
    ),
    "OHLA": (
        "ohla group",
        "obrascon huarte lain",
        "obrascón huarte laín",
    ),
    "ORYZON GENOMICS": (
        "oryzon genomics",
        "iadademstat",
        "vafidemstat",
    ),
    "PARLEM TELECOM": (
        "parlem telecom",
        "grupo parlem",
    ),
    "PHARMAMAR": (
        "pharmamar",
        "pharma mar",
        "zepzelca",
        "lurbinectedin",
        "yondelis",
        "trabectedin",
        "aplidin",
        "plitidepsin",
        "sylentis",
    ),
    "PROSEGUR": (
        "prosegur",
    ),
    "PROSEGUR CASH": (
        "prosegur cash",
    ),
    "PUIG": (
        "puig brands",
        "puig beauty",
        "charlotte tilbury",
        "rabanne",
        "carolina herrera",
        "jean paul gaultier",
    ),
    "REDEIA": (
        "redeia",
        "red electrica de espana",
        "red eléctrica de españa",
        "red electrica corporation",
        "hispasat",
    ),
    "REDEGAL": (
        "redegal",
    ),
    "REPSOL": (
        "repsol",
    ),
    "ROVI": (
        "laboratorios farmaceuticos rovi",
        "laboratorios farmacéuticos rovi",
        "rovi laboratories",
        "rovi pharma",
    ),
    "SACYR": (
        "sacyr",
    ),
    "SOLARIA": (
        "solaria energia",
        "solaria energía",
        "solaria power",
    ),
    "SOLTEC": (
        "soltec power",
        "soltec group",
    ),
    "SQUIRREL MEDIA": (
        "squirrel media",
    ),
    "TALGO": (
        "patentes talgo",
        "grupo talgo",
        "talgo trains",
    ),
    "TÉCNICAS REUNIDAS": (
        "tecnicas reunidas",
        "técnicas reunidas",
    ),
    "TELEFÓNICA": (
        "telefonica",
        "telefónica",
        "movistar",
        "o2 germany",
        "telefonica deutschland",
        "telefónica deutschland",
        "telefonica brasil",
        "telefónica brasil",
        "vivo brasil",
    ),
    "TUBACEX": (
        "tubacex",
    ),
    "TUBOS REUNIDOS": (
        "tubos reunidos",
    ),
    "UNICaja BANCO": (
        "unicaja banco",
        "unicaja bank",
    ),
    "VISCOFAN": (
        "viscofan",
    ),
}


SUFIJOS_SOCIALES = (
    " sociedad anonima",
    " sociedad limitada",
    " socimi",
    " s a",
    " s l",
    " sa",
    " sl",
    " plc",
    " limited",
    " ltd",
    " corporation",
    " corp",
    " group",
)


PALABRAS_NO_VALIDAS = {
    "grupo",
    "group",
    "holding",
    "holdings",
    "socimi",
    "company",
    "companies",
    "investment",
    "investments",
    "international",
    "global",
    "capital",
    "properties",
    "property",
    "energy",
    "energia",
    "solar",
}


def normalizar(valor: str) -> str:
    valor = html.unescape(valor)

    valor = unicodedata.normalize(
        "NFKD",
        valor,
    )

    valor = "".join(
        caracter
        for caracter in valor
        if not unicodedata.combining(caracter)
    )

    valor = valor.casefold()

    valor = re.sub(
        r"<[^>]+>",
        " ",
        valor,
    )

    valor = valor.replace("&", " and ")

    valor = re.sub(
        r"[^a-z0-9.+ -]",
        " ",
        valor,
    )

    return " ".join(valor.split())


def limpiar_nombre_social(nombre: str) -> str:
    nombre = normalizar(nombre)

    cambiado = True

    while cambiado:
        cambiado = False

        for sufijo in SUFIJOS_SOCIALES:
            if nombre.endswith(sufijo):
                nombre = nombre[
                    :-len(sufijo)
                ].strip()

                cambiado = True

    return nombre


def descargar(url: str) -> bytes:
    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 BloombergBMERS​​S/1.0"
            ),
            "Accept": (
                "application/json,"
                "application/rss+xml,"
                "application/xml,text/xml;q=0.9,"
                "*/*;q=0.8"
            ),
        },
    )

    with urllib.request.urlopen(
        peticion,
        timeout=60,
    ) as respuesta:
        contenido = respuesta.read()

    if not contenido:
        raise RuntimeError(
            f"Respuesta vacía: {url}"
        )

    return contenido


def construir_url_bme(
    trading_system: str,
    mtf_segment: str,
) -> str:
    parametros = {
        "ISIN": "",
        "sectorKey": "",
        "subsectorKey": "",
        "tradingSystem": trading_system,
        "mtfSegment": mtf_segment,
        "page": "0",
        "pageSize": "0",
    }

    return (
        BME_API
        + "?"
        + urllib.parse.urlencode(parametros)
    )


def crear_variantes_empresa(
    nombre: str,
    nombre_accion: str,
) -> set[str]:
    variantes = {
        normalizar(nombre),
        normalizar(nombre_accion),
        limpiar_nombre_social(nombre),
        limpiar_nombre_social(nombre_accion),
    }

    resultado: set[str] = set()

    for variante in variantes:
        variante = variante.strip(" .,-")

        if len(variante) < 4:
            continue

        if variante in PALABRAS_NO_VALIDAS:
            continue

        resultado.add(variante)

    return resultado


def cargar_empresas_bme() -> list[dict]:
    empresas_por_clave: dict[
        tuple[str, str],
        dict,
    ] = {}

    for mercado, configuracion in (
        MERCADOS_BME.items()
    ):
        url = construir_url_bme(
            configuracion["tradingSystem"],
            configuracion["mtfSegment"],
        )

        datos = json.loads(
            descargar(url).decode(
                "utf-8",
                errors="replace",
            )
        )

        registros = datos.get(
            "data",
            [],
        )

        print(
            f"{mercado}: "
            f"{len(registros)} empresas descargadas"
        )

        for registro in registros:
            nombre_legal = (
                registro.get("name")
                or ""
            ).strip()

            nombre_accion = (
                registro.get("shareName")
                or nombre_legal
            ).strip()

            if not nombre_accion:
                continue

            clave = (
                normalizar(nombre_accion),
                mercado,
            )

            variantes = crear_variantes_empresa(
                nombre_legal,
                nombre_accion,
            )

            if not variantes:
                continue

            empresas_por_clave[clave] = {
                "nombre": nombre_accion,
                "mercado": mercado,
                "isin": (
                    registro.get("isin")
                    or ""
                ),
                "variantes": variantes,
            }

    # Añade marcas, filiales y medicamentos que
    # no aparecen en el nombre oficial de BME.
    for nombre_alias, variantes_alias in (
        ALIAS_ADICIONALES.items()
    ):
        nombre_normalizado = normalizar(
            nombre_alias
        )

        coincidencias = [
            empresa
            for empresa
            in empresas_por_clave.values()
            if (
                nombre_normalizado
                in empresa["variantes"]
                or any(
                    nombre_normalizado
                    in variante
                    or variante
                    in nombre_normalizado
                    for variante
                    in empresa["variantes"]
                    if len(variante) >= 5
                )
            )
        ]

        if coincidencias:
            for empresa in coincidencias:
                empresa["variantes"].update(
                    normalizar(variante)
                    for variante
                    in variantes_alias
                )

        else:
            # Se mantiene el alias como apoyo por si
            # BME presenta temporalmente el nombre
            # de la compañía de otra forma.
            clave = (
                nombre_normalizado,
                "Cotizada en España",
            )

            empresas_por_clave[clave] = {
                "nombre": nombre_alias,
                "mercado": (
                    "Cotizada en España"
                ),
                "isin": "",
                "variantes": {
                    normalizar(variante)
                    for variante
                    in variantes_alias
                    if len(
                        normalizar(variante)
                    ) >= 4
                },
            }

    empresas = list(
        empresas_por_clave.values()
    )

    empresas.sort(
        key=lambda empresa: max(
            (
                len(variante)
                for variante
                in empresa["variantes"]
            ),
            default=0,
        ),
        reverse=True,
    )

    print(
        "Total de registros de empresas "
        f"utilizados: {len(empresas)}"
    )

    return empresas


def contiene_variante(
    contenido: str,
    variante: str,
) -> bool:
    patron = (
        r"(?<![a-z0-9])"
        + re.escape(variante)
        + r"(?![a-z0-9])"
    )

    return bool(
        re.search(
            patron,
            contenido,
        )
    )


def detectar_empresas(
    titulo: str,
    descripcion: str,
    empresas_bme: list[dict],
) -> list[dict]:
    contenido = normalizar(
        titulo + " " + descripcion
    )

    encontradas: list[dict] = []
    claves_vistas: set[
        tuple[str, str]
    ] = set()

    for empresa in empresas_bme:
        coincide = any(
            contiene_variante(
                contenido,
                variante,
            )
            for variante
            in empresa["variantes"]
        )

        if not coincide:
            continue

        clave = (
            normalizar(
                empresa["nombre"]
            ),
            empresa["mercado"],
        )

        if clave in claves_vistas:
            continue

        claves_vistas.add(clave)
        encontradas.append(empresa)

    return encontradas


def convertir_fecha(entrada) -> datetime:
    estructura = (
        entrada.get("published_parsed")
        or entrada.get("updated_parsed")
    )

    if estructura:
        return datetime(
            estructura.tm_year,
            estructura.tm_mon,
            estructura.tm_mday,
            estructura.tm_hour,
            estructura.tm_min,
            estructura.tm_sec,
            tzinfo=timezone.utc,
        )

    return datetime.now(
        timezone.utc
    )


def limpiar_resumen(valor: str) -> str:
    valor = re.sub(
        r"<[^>]+>",
        " ",
        valor,
    )

    valor = html.unescape(valor)

    return " ".join(
        valor.split()
    )


def leer_fuente_bloomberg(
    seccion: str,
    url: str,
    empresas_bme: list[dict],
) -> list[dict]:
    fuente = feedparser.parse(
        descargar(url)
    )

    if fuente.bozo and not fuente.entries:
        raise RuntimeError(
            str(fuente.bozo_exception)
        )

    resultados: list[dict] = []

    for entrada in fuente.entries:
        titulo = html.unescape(
            " ".join(
                entrada.get(
                    "title",
                    "",
                ).split()
            )
        )

        descripcion = limpiar_resumen(
            entrada.get(
                "summary",
                entrada.get(
                    "description",
                    "",
                ),
            )
        )

        enlace = entrada.get(
            "link",
            "",
        ).strip()

        guid = (
            entrada.get("id")
            or enlace
        )

        autor = (
            entrada.get("author")
            or "Bloomberg"
        )

        if not titulo or not enlace:
            continue

        empresas = detectar_empresas(
            titulo,
            descripcion,
            empresas_bme,
        )

        # Solo se guardan noticias en las que
        # aparece alguna empresa cotizada en BME.
        if not empresas:
            continue

        resultados.append(
            {
                "titulo": titulo,
                "descripcion": descripcion,
                "enlace": enlace,
                "guid": guid,
                "fecha": convertir_fecha(
                    entrada
                ),
                "autor": autor,
                "empresas": empresas,
                "secciones": {seccion},
            }
        )

    print(
        f"{seccion}: "
        f"{len(resultados)} noticias "
        "relacionadas con empresas de BME"
    )

    return resultados


def obtener_noticias(
    empresas_bme: list[dict],
) -> dict[str, dict]:
    noticias: dict[str, dict] = {}
    fuentes_correctas = 0

    for seccion, url in (
        FUENTES_BLOOMBERG.items()
    ):
        try:
            resultados = leer_fuente_bloomberg(
                seccion,
                url,
                empresas_bme,
            )

            fuentes_correctas += 1

            for noticia in resultados:
                clave = noticia[
                    "enlace"
                ].rstrip("/")

                if clave not in noticias:
                    noticias[clave] = noticia

                else:
                    noticias[clave][
                        "secciones"
                    ].update(
                        noticia["secciones"]
                    )

        except Exception as error:
            print(
                f"AVISO: {seccion}: {error}"
            )

    if fuentes_correctas == 0:
        raise RuntimeError(
            "No se ha podido leer ningún "
            "canal de Bloomberg."
        )

    print(
        "Total de noticias actuales "
        "sobre empresas de BME: "
        f"{len(noticias)}"
    )

    return noticias


def texto_elemento(
    elemento: ET.Element,
    nombre: str,
) -> str:
    nodo = elemento.find(nombre)

    if nodo is None or nodo.text is None:
        return ""

    return nodo.text.strip()


def cargar_anteriores() -> dict[str, ET.Element]:
    anteriores: dict[
        str,
        ET.Element,
    ] = {}

    if not SALIDA.exists():
        return anteriores

    try:
        raiz = ET.parse(
            SALIDA
        ).getroot()

        canal = raiz.find(
            "channel"
        )

        if canal is None:
            return anteriores

        for item in canal.findall("item"):
            clave = (
                texto_elemento(
                    item,
                    "link",
                )
                or texto_elemento(
                    item,
                    "guid",
                )
            ).rstrip("/")

            if clave:
                anteriores[clave] = (
                    copy.deepcopy(item)
                )

    except ET.ParseError:
        print(
            "El rss.xml anterior no era válido. "
            "Se reconstruirá."
        )

    return anteriores


def crear_descripcion(
    noticia: dict,
) -> str:
    partes: list[str] = []

    if noticia["descripcion"]:
        partes.append(
            "<p>"
            + html.escape(
                noticia["descripcion"]
            )
            + "</p>"
        )

    nombres = ", ".join(
        html.escape(
            empresa["nombre"]
        )
        for empresa
        in noticia["empresas"]
    )

    partes.append(
        "<p><strong>"
        "Empresas detectadas:"
        "</strong> "
        f"{nombres}</p>"
    )

    mercados: dict[str, list[str]] = {}

    for empresa in noticia["empresas"]:
        mercado = empresa["mercado"]

        mercados.setdefault(
            mercado,
            [],
        ).append(
            empresa["nombre"]
        )

    for mercado, empresas in mercados.items():
        listado = ", ".join(
            html.escape(empresa)
            for empresa in empresas
        )

        partes.append(
            "<p><strong>"
            f"{html.escape(mercado)}:"
            "</strong> "
            f"{listado}</p>"
        )

    secciones = ", ".join(
        sorted(
            noticia["secciones"]
        )
    )

    partes.append(
        "<p><strong>"
        "Fuente:"
        "</strong> "
        f"{html.escape(secciones)}</p>"
    )

    partes.append(
        "<p>El artículo completo puede "
        "requerir una suscripción a Bloomberg."
        "</p>"
    )

    return "".join(partes)


def crear_item(
    noticia: dict,
) -> ET.Element:
    item = ET.Element("item")

    empresas_titulo = ", ".join(
        empresa["nombre"]
        for empresa
        in noticia["empresas"]
    )

    titulo_rss = (
        f"[{empresas_titulo}] "
        f"{noticia['titulo']}"
    )

    ET.SubElement(
        item,
        "title",
    ).text = titulo_rss

    ET.SubElement(
        item,
        "link",
    ).text = noticia["enlace"]

    ET.SubElement(
        item,
        "guid",
        {"isPermaLink": "false"},
    ).text = noticia["guid"]

    ET.SubElement(
        item,
        "pubDate",
    ).text = (
        email.utils.format_datetime(
            noticia["fecha"]
        )
    )

    ET.SubElement(
        item,
        "description",
    ).text = crear_descripcion(
        noticia
    )

    ET.SubElement(
        item,
        "author",
    ).text = noticia["autor"]

    ET.SubElement(
        item,
        "category",
    ).text = "Empresas cotizadas en España"

    categorias_vistas: set[str] = set()

    for empresa in noticia["empresas"]:
        for categoria in (
            empresa["nombre"],
            empresa["mercado"],
        ):
            if categoria in categorias_vistas:
                continue

            categorias_vistas.add(categoria)

            ET.SubElement(
                item,
                "category",
            ).text = categoria

    for seccion in sorted(
        noticia["secciones"]
    ):
        ET.SubElement(
            item,
            "category",
        ).text = seccion

    return item


def fecha_item(item: ET.Element) -> datetime:
    try:
        resultado = (
            email.utils
            .parsedate_to_datetime(
                texto_elemento(
                    item,
                    "pubDate",
                )
            )
        )

        if resultado.tzinfo is None:
            resultado = resultado.replace(
                tzinfo=timezone.utc
            )

        return resultado

    except (TypeError, ValueError):
        return datetime.min.replace(
            tzinfo=timezone.utc
        )


def escribir_rss(
    items: dict[str, ET.Element],
) -> None:
    rss = ET.Element(
        "rss",
        {"version": "2.0"},
    )

    canal = ET.SubElement(
        rss,
        "channel",
    )

    ET.SubElement(
        canal,
        "title",
    ).text = (
        "Bloomberg — Empresas españolas, "
        "BME Growth y BME Scaleup"
    )

    ET.SubElement(
        canal,
        "link",
    ).text = (
        "https://www.bloomberg.com/europe"
    )

    ET.SubElement(
        canal,
        "description",
    ).text = (
        "Noticias de Bloomberg relacionadas "
        "con empresas del Mercado Continuo, "
        "BME Growth y BME Scaleup."
    )

    ET.SubElement(
        canal,
        "language",
    ).text = "es-ES"

    ET.SubElement(
        canal,
        "lastBuildDate",
    ).text = (
        email.utils.format_datetime(
            datetime.now(timezone.utc)
        )
    )

    ordenados = sorted(
        items.values(),
        key=fecha_item,
        reverse=True,
    )[:MAXIMO_GUARDADOS]

    for item in ordenados:
        canal.append(
            copy.deepcopy(item)
        )

    arbol = ET.ElementTree(rss)

    ET.indent(
        arbol,
        space="  ",
    )

    arbol.write(
        SALIDA,
        encoding="utf-8",
        xml_declaration=True,
    )


def dentro_del_horario() -> bool:
    # Las ejecuciones manuales siempre funcionan.
    if os.environ.get(
        "GITHUB_EVENT_NAME",
        "",
    ) == "workflow_dispatch":
        return True

    ahora = datetime.now(
        ZoneInfo("Europe/Madrid")
    )

    # Domingo no se ejecuta.
    if ahora.weekday() == 6:
        print(
            "Hoy es domingo. "
            "No se actualiza el RSS."
        )
        return False

    # Desde las 07:00 hasta las 22:59.
    if not 7 <= ahora.hour <= 22:
        print(
            "Fuera del horario: "
            f"{ahora:%Y-%m-%d %H:%M %Z}"
        )
        return False

    return True


def main() -> None:
    if not dentro_del_horario():
        return

    empresas_bme = cargar_empresas_bme()

    if not empresas_bme:
        raise RuntimeError(
            "No se ha descargado ninguna "
            "empresa desde BME."
        )

    noticias = obtener_noticias(
        empresas_bme
    )

    guardados = cargar_anteriores()

    nuevas = 0

    for noticia in sorted(
        noticias.values(),
        key=lambda valor: valor["fecha"],
        reverse=True,
    ):
        clave = noticia[
            "enlace"
        ].rstrip("/")

        if clave not in guardados:
            nuevas += 1

        guardados[clave] = crear_item(
            noticia
        )

    escribir_rss(guardados)

    print(
        f"Noticias nuevas: {nuevas}"
    )

    print(
        "Total de noticias conservadas: "
        f"{len(guardados)}"
    )


if __name__ == "__main__":
    main()
