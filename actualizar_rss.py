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


FUENTES_BLOOMBERG = {
    "Mercados": (
        "https://feeds.bloomberg.com/"
        "markets/news.rss"
    ),
    "Empresas e industrias": (
        "https://feeds.bloomberg.com/"
        "industries/news.rss"
    ),
    "Tecnologia": (
        "https://feeds.bloomberg.com/"
        "technology/news.rss"
    ),
    "Economia": (
        "https://feeds.bloomberg.com/"
        "economics/news.rss"
    ),
    "Politica": (
        "https://feeds.bloomberg.com/"
        "politics/news.rss"
    ),
}


BME_API = (
    "https://apiweb.bolsasymercados.es/"
    "Market/v1/EQ/ListedCompanies"
)


MERCADOS_BME = {
    "Mercado Continuo": (
        "SIBE",
        "",
    ),
    "BME Growth": (
        "MTF",
        "BMEGrowth",
    ),
    "BME Scaleup": (
        "MTF",
        "BMEScaleup",
    ),
}


# Marcas, filiales y productos que Bloomberg
# puede usar en lugar del nombre bursatil.
ALIAS = {
    "ACCIONA": (
        "acciona",
    ),
    "ACCIONA ENERGIA": (
        "acciona energy",
        "acciona energia",
    ),
    "ACERINOX": (
        "acerinox",
        "north american stainless",
        "vdm metals",
    ),
    "ACS": (
        "acs group",
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
    "BANCO SABADELL": (
        "banco sabadell",
        "sabadell bank",
        "tsb banking",
    ),
    "BANCO SANTANDER": (
        "banco santander",
        "santander bank",
        "santander group",
        "openbank",
    ),
    "BBVA": (
        "bbva",
        "banco bilbao vizcaya",
    ),
    "CAIXABANK": (
        "caixabank",
        "banco bpi",
    ),
    "CAF": (
        "caf rail",
        "caf group",
        "solaris bus",
    ),
    "CELLNEX": (
        "cellnex",
        "cellnex telecom",
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
    ),
    "ELECNOR": (
        "elecnor",
        "enerfin",
    ),
    "FCC": (
        "fcc group",
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
    ),
    "HBX GROUP": (
        "hbx group",
        "hotelbeds",
    ),
    "IAG": (
        "international airlines group",
        "british airways",
        "iberia airlines",
        "aer lingus",
        "vueling",
    ),
    "IBERDROLA": (
        "iberdrola",
        "avangrid",
        "scottishpower",
    ),
    "INDITEX": (
        "inditex",
        "zara",
        "bershka",
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
    "MELIA HOTELS": (
        "melia hotels",
        "melia hotel",
    ),
    "MFE-MEDIAFOREUROPE": (
        "mediaforeurope",
        "mediaset espana",
    ),
    "NATURGY": (
        "naturgy",
        "gas natural fenosa",
    ),
    "OHLA": (
        "ohla group",
        "obrascon huarte lain",
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
        "zepzelca",
        "lurbinectedin",
        "yondelis",
        "trabectedin",
        "aplidin",
        "plitidepsin",
        "sylentis",
    ),
    "PUIG": (
        "puig beauty",
        "charlotte tilbury",
        "rabanne",
        "carolina herrera",
        "jean paul gaultier",
    ),
    "REDEIA": (
        "redeia",
        "red electrica de espana",
        "hispasat",
    ),
    "REDEGAL": (
        "redegal",
    ),
    "ROVI": (
        "laboratorios rovi",
        "rovi pharma",
    ),
    "TALGO": (
        "patentes talgo",
        "grupo talgo",
        "talgo trains",
    ),
    "TELEFONICA": (
        "telefonica",
        "movistar",
        "o2 germany",
        "telefonica deutschland",
        "telefonica brasil",
        "vivo brasil",
    ),
}


SUFIJOS = (
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
)


NO_VALIDAS = {
    "group",
    "grupo",
    "holding",
    "holdings",
    "socimi",
    "company",
    "companies",
    "international",
    "global",
    "capital",
    "properties",
    "property",
    "energy",
    "energia",
    "solar",
    "investment",
    "investments",
}


def normalizar(valor: str) -> str:
    valor = html.unescape(
        valor or ""
    )

    valor = unicodedata.normalize(
        "NFKD",
        valor,
    )

    valor = "".join(
        caracter
        for caracter in valor
        if not unicodedata.combining(
            caracter
        )
    )

    valor = valor.casefold().replace(
        "&",
        " and ",
    )

    valor = re.sub(
        r"<[^>]+>",
        " ",
        valor,
    )

    valor = re.sub(
        r"[^a-z0-9.+ -]",
        " ",
        valor,
    )

    return " ".join(
        valor.split()
    )


def limpiar_nombre(valor: str) -> str:
    valor = normalizar(valor)

    cambio = True

    while cambio:
        cambio = False

        for sufijo in SUFIJOS:
            if valor.endswith(sufijo):
                valor = valor[
                    :-len(sufijo)
                ].strip()

                cambio = True

    return valor.strip(
        " .,-"
    )


def descargar(url: str) -> bytes:
    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": (
                "application/json,"
                "application/rss+xml,"
                "application/xml,"
                "text/xml;q=0.9,"
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
            f"Respuesta vacia: {url}"
        )

    return contenido


def construir_url_bme(
    sistema: str,
    segmento: str,
) -> str:
    parametros = {
        "ISIN": "",
        "sectorKey": "",
        "subsectorKey": "",
        "tradingSystem": sistema,
        "mtfSegment": segmento,
        "page": "0",
        "pageSize": "0",
    }

    return (
        BME_API
        + "?"
        + urllib.parse.urlencode(
            parametros
        )
    )


def crear_variantes(
    nombre_legal: str,
    nombre_accion: str,
) -> set[str]:
    posibles = {
        normalizar(nombre_legal),
        normalizar(nombre_accion),
        limpiar_nombre(nombre_legal),
        limpiar_nombre(nombre_accion),
    }

    return {
        variante
        for variante in posibles
        if (
            len(variante) >= 4
            and variante not in NO_VALIDAS
        )
    }


def cargar_empresas_bme() -> list[dict]:
    empresas: dict[
        tuple[str, str],
        dict,
    ] = {}

    for mercado, configuracion in (
        MERCADOS_BME.items()
    ):
        sistema, segmento = configuracion

        url = construir_url_bme(
            sistema,
            segmento,
        )

        contenido = descargar(url)

        respuesta = json.loads(
            contenido.decode(
                "utf-8",
                errors="replace",
            )
        )

        registros = respuesta.get(
            "data",
            [],
        )

        print(
            f"{mercado}: "
            f"{len(registros)} empresas"
        )

        for registro in registros:
            nombre_legal = (
                registro.get("name")
                or ""
            ).strip()

            nombre = (
                registro.get("shareName")
                or nombre_legal
            ).strip()

            candidatos = crear_variantes(
                nombre_legal,
                nombre,
            )

            if not nombre or not candidatos:
                continue

            clave = (
                normalizar(nombre),
                mercado,
            )

            empresas[clave] = {
                "nombre": nombre,
                "mercado": mercado,
                "isin": (
                    registro.get("isin")
                    or ""
                ),
                "variantes": candidatos,
            }

    # Añade marcas, filiales y productos.
    for nombre_alias, lista_alias in (
        ALIAS.items()
    ):
        buscado = normalizar(
            nombre_alias
        )

        coincidencias = [
            empresa
            for empresa
            in empresas.values()
            if (
                buscado
                in empresa["variantes"]
                or normalizar(
                    empresa["nombre"]
                ) == buscado
            )
        ]

        if coincidencias:
            for empresa in coincidencias:
                empresa[
                    "variantes"
                ].update(
                    normalizar(alias)
                    for alias in lista_alias
                )

        else:
            clave = (
                buscado,
                "Cotizada en Espana",
            )

            empresas[clave] = {
                "nombre": nombre_alias,
                "mercado": (
                    "Cotizada en Espana"
                ),
                "isin": "",
                "variantes": {
                    normalizar(alias)
                    for alias in lista_alias
                    if len(
                        normalizar(alias)
                    ) >= 4
                },
            }

    resultado = list(
        empresas.values()
    )

    resultado.sort(
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
        "Total de empresas controladas: "
        f"{len(resultado)}"
    )

    return resultado


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
    resumen: str,
    empresas_bme: list[dict],
) -> list[dict]:
    contenido = normalizar(
        titulo + " " + resumen
    )

    encontradas: list[dict] = []
    vistas: set[tuple[str, str]] = set()

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

        if clave in vistas:
            continue

        vistas.add(clave)
        encontradas.append(empresa)

    return encontradas


def fecha_entrada(entrada) -> datetime:
    fecha = (
        entrada.get("published_parsed")
        or entrada.get("updated_parsed")
    )

    if fecha:
        return datetime(
            fecha.tm_year,
            fecha.tm_mon,
            fecha.tm_mday,
            fecha.tm_hour,
            fecha.tm_min,
            fecha.tm_sec,
            tzinfo=timezone.utc,
        )

    return datetime.now(
        timezone.utc
    )


def limpiar_resumen(valor: str) -> str:
    valor = re.sub(
        r"<[^>]+>",
        " ",
        valor or "",
    )

    valor = html.unescape(valor)

    return " ".join(
        valor.split()
    )


def obtener_noticias(
    empresas_bme: list[dict],
) -> dict[str, dict]:
    noticias: dict[str, dict] = {}
    fuentes_correctas = 0

    for seccion, url in (
        FUENTES_BLOOMBERG.items()
    ):
        try:
            fuente = feedparser.parse(
                descargar(url)
            )

            if (
                fuente.bozo
                and not fuente.entries
            ):
                raise RuntimeError(
                    str(
                        fuente.bozo_exception
                    )
                )

            fuentes_correctas += 1
            encontradas = 0

            for entrada in fuente.entries:
                titulo = html.unescape(
                    " ".join(
                        entrada.get(
                            "title",
                            "",
                        ).split()
                    )
                )

                resumen = limpiar_resumen(
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

                if not titulo or not enlace:
                    continue

                empresas = detectar_empresas(
                    titulo,
                    resumen,
                    empresas_bme,
                )

                if not empresas:
                    continue

                encontradas += 1
                clave = enlace.rstrip("/")

                if clave not in noticias:
                    noticias[clave] = {
                        "titulo": titulo,
                        "resumen": resumen,
                        "enlace": enlace,
                        "guid": (
                            entrada.get("id")
                            or enlace
                        ),
                        "fecha": fecha_entrada(
                            entrada
                        ),
                        "autor": (
                            entrada.get("author")
                            or "Bloomberg"
                        ),
                        "empresas": empresas,
                        "secciones": {
                            seccion
                        },
                    }

                else:
                    noticias[clave][
                        "secciones"
                    ].add(seccion)

            print(
                f"{seccion}: "
                f"{encontradas} noticias "
                "de empresas BME"
            )

        except Exception as error:
            print(
                f"AVISO: {seccion}: {error}"
            )

    if fuentes_correctas == 0:
        raise RuntimeError(
            "No se pudo leer ningun "
            "canal de Bloomberg"
        )

    print(
        "Noticias actuales relacionadas "
        f"con empresas BME: {len(noticias)}"
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
        canal = (
            ET.parse(SALIDA)
            .getroot()
            .find("channel")
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
            "El rss.xml no era valido "
            "y se reconstruira"
        )

    return anteriores


def crear_item(noticia: dict) -> ET.Element:
    item = ET.Element("item")

    nombres = ", ".join(
        empresa["nombre"]
        for empresa
        in noticia["empresas"]
    )

    ET.SubElement(
        item,
        "title",
    ).text = (
        f"[{nombres}] "
        f"{noticia['titulo']}"
    )

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

    partes: list[str] = []

    if noticia["resumen"]:
        partes.append(
            "<p>"
            + html.escape(
                noticia["resumen"]
            )
            + "</p>"
        )

    partes.append(
        "<p><strong>"
        "Empresas BME:"
        "</strong> "
        f"{html.escape(nombres)}</p>"
    )

    mercados = sorted(
        {
            empresa["mercado"]
            for empresa
            in noticia["empresas"]
        }
    )

    partes.append(
        "<p><strong>"
        "Mercados:"
        "</strong> "
        f"{html.escape(', '.join(mercados))}"
        "</p>"
    )

    partes.append(
        "<p>El articulo completo puede "
        "requerir suscripcion a Bloomberg."
        "</p>"
    )

    ET.SubElement(
        item,
        "description",
    ).text = "".join(partes)

    ET.SubElement(
        item,
        "author",
    ).text = noticia["autor"]

    ET.SubElement(
        item,
        "category",
    ).text = "Empresas cotizadas en Espana"

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
        fecha = (
            email.utils
            .parsedate_to_datetime(
                texto_elemento(
                    item,
                    "pubDate",
                )
            )
        )

        if fecha.tzinfo is None:
            fecha = fecha.replace(
                tzinfo=timezone.utc
            )

        return fecha

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
        "Bloomberg - Mercado Continuo, "
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
    # La ejecución manual siempre funciona.
    if os.environ.get(
        "GITHUB_EVENT_NAME",
        "",
    ) == "workflow_dispatch":
        return True

    ahora = datetime.now(
        ZoneInfo("Europe/Madrid")
    )

    # De lunes a sábado, 07:00-22:59.
    if (
        ahora.weekday() == 6
        or not 7 <= ahora.hour <= 22
    ):
        print(
            "Fuera de horario: "
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
            "No se descargaron empresas "
            "desde BME"
        )

    noticias = obtener_noticias(
        empresas_bme
    )

    guardados = cargar_anteriores()
    nuevas = 0

    noticias_ordenadas = sorted(
        noticias.values(),
        key=lambda noticia: noticia["fecha"],
        reverse=True,
    )

    for noticia in noticias_ordenadas:
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
        "Total conservadas: "
        f"{len(guardados)}"
    )


if __name__ == "__main__":
    main()
