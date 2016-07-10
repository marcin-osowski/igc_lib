import math

EARTH_RADIUS_KM = 6371.0


def sphere_distance(lat1, lon1, lat2, lon2):
    """Computes the great circle distance on a unit sphere.

    All angles and the return value are in radians.

    Args:
        lat1: A float, latitude of the first point.
        lon1: A float, longitude of the first point.
        lat2: A float, latitude of the second point.
        lon2: A float, latitude of the second point.

    Returns:
        The computed great circle distance on a sphere.
    """
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (math.sin(dlat/2)**2 +
         math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
    return 2.0 * math.asin(math.sqrt(a))


def earth_distance(lat1, lon1, lat2, lon2):
    """Computes Earth distance between two points, in kilometers.

    Input angles are in degrees, WGS-84. Output is in kilometers.

    Args:
        lat1: A float, latitude of the first point.
        lon1: A float, longitude of the first point.
        lat2: A float, latitude of the second point.
        lon2: A float, latitude of the second point.

    Returns:
        A float, the computed Earth distance.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    return EARTH_RADIUS_KM * sphere_distance(lat1, lon1, lat2, lon2)


def bearing_to(lat1, lon1, lat2, lon2):
    """Computes bearing between the current point and the heading point.

    Input angles and the output bearing are in degrees. Bearing
    is 0.0 when we are facing north, +90.0 when facing east,
    -90.0 when facing west, +/-180.0 when facing south.

    Args:
        lat1: A float, latitude of the current point.
        lon1: A float, longitude of the current point.
        lat2: A float, latitude of the heading to point.
        lon2: A float, latitude of the heading to point.

    Returns:
        A float, the heading (north = 0.0).
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dLon = lon2 - lon1
    y = math.sin(dLon) * math.cos(lat2)
    x = (math.cos(lat1) * math.sin(lat2) -
         math.sin(lat1) * math.cos(lat2) * math.cos(dLon))
    return math.degrees(math.atan2(y, x))


def sphere_angle(lat1, lon1, lat, lon, lat2, lon2):
    """Computes the angle on a sphere given three points.

    Input angles and the output angle are in degrees. The first
    input point denotes the first side of the angle, the second
    input point is the vertex of the angle, the third input point
    denotes the second side of the angle.

    Example (output=90.0):
    (lat=0.0, lon=0.0) -------- (lat1=0.0, lon1=10.0)
        |
        |
    (lat2=-20.0, lon2=0.0)

    Args:
        lat1: a float, latitude of the first point
        lon1: a float, longitude of the first point
        lat: a float, latitude of the vertex.
        lon: a float, longitude of the vertex.
        lat2: a float, latitude of the second point.
        lon2: a float, latitude of the second point.

    Returns:
        A float, the angle between the points.
    """
    lat1, lon1, lat, lon, lat2, lon2 = map(
        math.radians, [lat1, lon1, lat, lon, lat2, lon2])
    side1 = sphere_distance(lat, lon, lat1, lon1)
    side2 = sphere_distance(lat, lon, lat2, lon2)
    opposite = sphere_distance(lat1, lon1, lat2, lon2)
    cosine = (math.cos(opposite) - math.cos(side1) * math.cos(side2))
    cosine /= (math.sin(side1) * math.sin(side2))

    if cosine > 1.0:
        cosine = 1.0
    if cosine < -1.0:
        cosine = -1.0
    angle = math.acos(cosine)
    return math.degrees(angle)
