# -*- file: nextcloud/tools/nextcloud_xml_utils.py -*-

import xml.etree.ElementTree as ET

def get_propfind_body():
    """
    Возвращает XML-строку для PROPFIND (запрос props: d:resourcetype, oc:fileid).
    """
    propfind = ET.Element('d:propfind', xmlns="DAV:")
    prop = ET.SubElement(propfind, 'd:prop')
    ET.SubElement(prop, 'd:resourcetype')
    ET.SubElement(prop, 'oc:fileid', xmlns="http://owncloud.org/ns")
    return ET.tostring(propfind, encoding='utf-8', method='xml').decode('utf-8')

def get_search_body(file_id):
    """
    Генерирует XML для запроса SEARCH по d:prop -> oc:fileid (равный file_id).

    :param file_id: ID файла для поиска
    :return: XML-строка для запроса SEARCH
    """
    search = ET.Element('d:searchrequest', xmlns="DAV:")
    prop = ET.SubElement(search, 'd:basicsearch')
    select = ET.SubElement(prop, 'd:select')
    prop_elem = ET.SubElement(select, 'd:prop')
    ET.SubElement(prop_elem, 'oc:fileid', xmlns="http://owncloud.org/ns")

    from_elem = ET.SubElement(prop, 'd:from')
    scope = ET.SubElement(from_elem, 'd:scope')
    ET.SubElement(scope, 'd:href').text = '/'
    ET.SubElement(scope, 'd:depth').text = 'infinity'

    where = ET.SubElement(prop, 'd:where')
    equals = ET.SubElement(where, 'd:eq')
    prop_elem = ET.SubElement(equals, 'd:prop')
    ET.SubElement(prop_elem, 'oc:fileid', xmlns="http://owncloud.org/ns")
    literal = ET.SubElement(equals, 'd:literal')
    literal.text = str(file_id)

    return ET.tostring(search, encoding='utf-8', method='xml').decode('utf-8')

def parse_node_data(xml_response):
    """
    Парсит XML-ответ, извлекает oc:fileid (очищает его до int) и d:href (путь).
    Поддерживает как PROPFIND, так и SEARCH.

    :param xml_response: XML-строка ответа от сервера
    :return: Кортеж (fileid, href)
    """
    try:
        root = ET.fromstring(xml_response)
        namespace = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        fileid_elem = root.find('.//oc:fileid', namespace)
        href_elem = root.find('.//d:href', namespace)

        fileid = int(fileid_elem.text) if fileid_elem is not None else None
        href = href_elem.text if href_elem is not None else None

        return fileid, href
    except (ET.ParseError, AttributeError, ValueError) as e:
        raise ValueError(f"Ошибка при парсинге XML ответа: {e}")
    
# End of file nextcloud/tools/nextcloud_xml_utils.py