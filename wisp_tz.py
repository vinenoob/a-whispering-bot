from dateutil.tz import gettz

tzinfos = {
    "EST": gettz("US/Eastern"),
    "ET": gettz("US/Eastern"),
    "CST": gettz("US/Central"),
    "CT": gettz("US/Central"),
    "MST": gettz("US/Mountain"),
    "MT": gettz("US/Mountain"),
    "PST": gettz("US/Pacific"),
    "PT": gettz("US/Pacific"),
}

for tz in tzinfos.keys():
    tzinfos[tz.lower()] = tzinfos[tz]