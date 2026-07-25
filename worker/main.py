from datetime import UTC, datetime, timedelta

import numpy as np
from astropy import units
from astropy.coordinates import ITRS, TEME, CartesianRepresentation
from astropy.time import Time
from sgp4.api import Satrec, jday

# 1. Ваши строки TLE (берём Transit 5B-4 из вашего списка)
# Убираем имя спутника, оставляем только 2 строки данных
line1 = "1 00897U 64063B   26204.62860723  .00000029  00000+0  29249-4 0  9991"
line2 = "2 00897  90.2324  76.3815 0021588  73.9531 313.3921 13.53738601 50158"

# 2. Инициализируем спутник в модели SGP4
satellite = Satrec.twoline2rv(line1, line2)

# 3. Задаем время расчета (строго в UTC!)
start_time = datetime.now(UTC)
time_steps = [start_time + timedelta(minutes=i) for i in range(100)]

years = np.array([t.year for t in time_steps])
months = np.array([t.month for t in time_steps])
days = np.array([t.day for t in time_steps])
hours = np.array([t.hour for t in time_steps])
minutes = np.array([t.minute for t in time_steps])
seconds = np.array([t.second + t.microsecond / 1e6 for t in time_steps])

jd, fr = jday(years, months, days, hours, minutes, seconds)

error_codes, positions, velocities = satellite.sgp4_array(jd, fr)

astropy_times = Time(time_steps)
# Создаем 3D-картезианские координаты в системе TEME (в метрах, поэтому * 1000)
teme_coords = TEME(
    CartesianRepresentation(positions.T * 1000 * units.m),
    obstime=astropy_times,
)

# Трансформируем в ITRS (земная вращающаяся система координат)
itrs_coords = teme_coords.transform_to(ITRS(obstime=astropy_times))

# Извлекаем широту, долготу и высоту над геоидом Земли
ellipsoid_coords = itrs_coords.earth_location

latitudes = ellipsoid_coords.lat.deg  # Массив широт (-90 до 90)
longitudes = ellipsoid_coords.lon.deg  # Массив долгот (-180 до 180)
heights = ellipsoid_coords.height.to("km").value  # Высота в км


time_strings = astropy_times.isot
# Склеиваем всё в одну матрицу (100 строк, 4 колонки)
# Для этого переводим время в массив объектов или строк
matrix = np.column_stack((time_strings, latitudes, longitudes, heights))


trajectory_output = [
    {
        "timestamp": row[0],
        "latitude": float(row[1]),
        "longitude": float(row[2]),
        "height_km": float(row[3]),
    }
    for row in matrix
]


print(trajectory_output)

# print(f"Первая точка: Широта {latitudes[0]:.4f}, Долгота {longitudes[0]:.4f}, Высота {heights[0]:.2f} км")


# Преобразуем время в Юлианскую дату, которую требует SGP4
# jd, fr = satellite.jdsatepoch, 0.0  # Или используйте текущие jd, fr для нужного момента

# Альтернативный точный способ для текущего времени:
# current_time = start_time
# trajectory = []

# while current_time <= end_time:

#     jd, fr = jday(
#         current_time.year,
#         current_time.month,
#         current_time.day,
#         current_time.hour,
#         current_time.minute,
#         current_time.second + current_time.microsecond / 1e6,
#     )

#     # 4. Выполняем расчет ( propagate )
#     error_code, position, velocity = satellite.sgp4(jd, fr)

#     # 5. Выводим результат
#     if error_code == 0:

#         trajectory.append(
#             {"time": current_time, "position": position, "velocity": velocity}
#         )

#         print(
#             f"{current_time.strftime('%H:%M:%S'):<12} | "
#             f"{position[0]:<10.2f} | "
#             f"{position[1]:<10.2f} | "
#             f"{position[2]:<10.2f}"
#         )
#     else:
#         print(f"Ошибка на шаге {current_time}: код {error_code}")

#     current_time += step_size
