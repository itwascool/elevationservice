import logging
import traceback
from flask import Flask, request, Response, jsonify
import rasterio
from shapely import wkt
import json
import sys

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.debug = True

elevation_file = '/Users/damirlutfullin/PycharmProjects/elevationservis/srtm_N55E160.tif'
def get_elevation(lat, lon):
    logger.info("Получение высоты для координат: lat=%f, lon=%f", lat, lon)
    coords = ((lon, lat), (lon, lat))
    try:
        with rasterio.open(elevation_file) as src:
            logger.info("Файл высот успешно открыт.")
            vals = src.sample(coords)
            for val in vals:
                elevation = val[0]
                logger.info("Полученная высота: %d", int(elevation))
                return int(elevation)
            logger.warning("Нет данных для координат: lat=%f, lon=%f", lat, lon)
    except Exception as e:
        logger.error("Ошибка при получении высоты: %s", str(e))
        return None


@app.errorhandler(Exception)
def special_exception_handler(error):

    result = {
        'message': str(error),
        'traceback': traceback.format_exc()
    }

    if hasattr(error, 'status'):
        status = error.status
    else:
        status = 500
    return jsonify(result), status

def parse_wkt(wkt_geom):
    logger.info("Полученный WKT: %s", wkt_geom)

    try:
        geom = wkt.loads(wkt_geom)  # Попытка распарсить WKT
        logger.info("Успешно распарсено WKT в геометрию: %s", geom)
        return geom
    except Exception as e:
        logger.error("Ошибка парсинга WKT: %s", e)
        return None


@app.route('/elevation', methods=['GET'])
def elevation_route():
    logger.info("Поступил запрос на /elevation")
    wkt_geom = request.args.get('wkt')
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    heights = []
    all_lat_lon = []
    parse_wkt(wkt_geom)

    if wkt_geom:
        logger.info("Обработка WKT геометрии")
        try:
            geom = wkt.loads(wkt_geom)
            if geom.is_empty:
                return Response(json.dumps({"error": "Геометрия пуста"}, ensure_ascii=False).encode('utf8'), mimetype='application/json; charset=utf-8'), 404
            if not geom.is_valid:
                return Response(json.dumps({"error": "Геометрия невалидна"}, ensure_ascii=False).encode('utf8'), mimetype='application/json; charset=utf-8'), 404

            if geom.geom_type == 'Polygon':
                coords = list(geom.exterior.coords)
                logger.info("Координаты: %s", coords)
            else:
                return Response(json.dumps({"error": "Ожидался POLYGON"}, ensure_ascii=False).encode('utf8'), mimetype='application/json; charset=utf-8'), 404

            elevation = []
            for coord in coords:
                elevation = get_elevation(coord[1], coord[0])
                if elevation is not None:
                    heights.append(elevation)
                    all_lat_lon.append((coord[1], coord[0]))  # Сохраняем lat, lon
                else:
                    logger.error("Не удалось получить высоту для координат: lat=%f, lon=%f", coord[1], coord[0])
                    return Response(json.dumps({"error": "Не удалось получить высоту для одной из координат"}, ensure_ascii=False).encode('utf8'), mimetype='application/json; charset=utf-8'), 404
            lat, lon = coords[-1][1], coords[-1][0]
            logger.info("Обработанные высоты: %s", heights)
        except Exception as e:
            logger.error("Ошибка: Неверный WKT формат. Подробности: %s", e)
            return Response(json.dumps({"error": "Неверный WKT формат"}, ensure_ascii=False).encode('utf8'), mimetype='application/json; charset=utf-8'), 404

    # Получение диапазона высот
    min_height = min(heights) if heights else None
    max_height = max(heights) if heights else None

    # Находим наименьшие и наибольшие lat, lon
    min_lat = min(all_lat_lon, key=lambda x: x[0])[0] if all_lat_lon else None
    max_lat = max(all_lat_lon, key=lambda x: x[0])[0] if all_lat_lon else None
    min_lon = min(all_lat_lon, key=lambda x: x[1])[1] if all_lat_lon else None
    max_lon = max(all_lat_lon, key=lambda x: x[1])[1] if all_lat_lon else None

    elevation_data = {
        "heights": [min_height, max_height],
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "latitude": lat,
        "longitude": lon
    }
    logger.info("Успешное получение высот: %s", str(heights))
    return Response(json.dumps(elevation_data, ensure_ascii=False).encode('utf8'), mimetype='application/json; charset=utf-8')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4040)