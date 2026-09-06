from __future__ import annotations

import copy
import email.utils
import html
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser


SALIDA = Path("rss.xml")
MAXIMO_GUARDADOS = 2500


# Canales RSS oficiales públicos de Bloomberg.
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
    "Bloomberg Wealth": (
        "https://feeds.bloomberg.com/"
        "wealth/news.rss"
    ),
    "Bloomberg Businessweek": (
        "https://feeds.bloomberg.com/"
        "businessweek/news.rss"
    ),
}


def descargar(url: str) -> bytes:
    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": (
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


def limpiar_texto(valor: str) -> str:
    valor = valor or ""

    valor = re.sub(
        r"<[^>]+>",
        " ",
        valor,
    )

    valor = html.unescape(valor)

    return " ".join(
        valor.split()
    )


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


def leer_fuente(
    seccion: str,
    url: str,
) -> list[dict]:
    contenido = descargar(url)

    fuente = feedparser.parse(
        contenido
    )

    if fuente.bozo and not fuente.entries:
        raise RuntimeError(
            str(fuente.bozo_exception)
        )

    resultados: list[dict] = []

    for entrada in fuente.entries:
        titulo = limpiar_texto(
            entrada.get(
                "title",
                "",
            )
        )

        descripcion = limpiar_texto(
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

        if (
            not titulo
            or not enlace
            or not guid
        ):
            continue

        resultados.append(
            {
                "titulo": titulo,
                "descripcion": descripcion,
                "enlace": enlace,
                "guid": guid,
                "autor": autor,
                "fecha": convertir_fecha(
                    entrada
                ),
                "secciones": {seccion},
            }
        )

    print(
        f"{seccion}: "
        f"{len(resultados)} noticias"
    )

    return resultados


def obtener_noticias() -> dict[str, dict]:
    noticias: dict[str, dict] = {}
    fuentes_correctas = 0

    for seccion, url in (
        FUENTES_BLOOMBERG.items()
    ):
        try:
            resultados = leer_fuente(
                seccion,
                url,
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
            "No se ha podido descargar "
            "ningun canal de Bloomberg."
        )

    print(
        "Total de noticias unicas: "
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
            "El rss.xml anterior no era valido. "
            "Se reconstruira."
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

    secciones = ", ".join(
        sorted(
            noticia["secciones"]
        )
    )

    partes.append(
        "<p><strong>"
        "Secciones:"
        "</strong> "
        f"{html.escape(secciones)}</p>"
    )

    partes.append(
        "<p>El articulo completo puede "
        "requerir una suscripcion a Bloomberg."
        "</p>"
    )

    return "".join(partes)


def crear_item(
    noticia: dict,
) -> ET.Element:
    item = ET.Element("item")

    ET.SubElement(
        item,
        "title",
    ).text = noticia["titulo"]

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
    ).text = "Bloomberg"

    for seccion in sorted(
        noticia["secciones"]
    ):
        ET.SubElement(
            item,
            "category",
        ).text = seccion

    return item


def fecha_item(
    item: ET.Element,
) -> datetime:
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
        "Bloomberg — Todas las noticias"
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
        "Todas las noticias disponibles en "
        "los canales publicos de Bloomberg: "
        "mercados, empresas, tecnologia, "
        "economia, politica y patrimonio."
    )

    ET.SubElement(
        canal,
        "language",
    ).text = "en"

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

    # De lunes a sábado.
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

    noticias = obtener_noticias()
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
        "Noticias encontradas ahora: "
        f"{len(noticias)}"
    )

    print(
        "Total conservadas: "
        f"{len(guardados)}"
    )


if __name__ == "__main__":
    main()
