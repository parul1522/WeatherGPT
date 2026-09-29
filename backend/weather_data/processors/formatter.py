def format_forecast(data: dict) -> dict:
    daily = data["daily"]

    result = []

    for i in range(len(daily["time"])):
        result.append({
            "date": daily["time"][i],
            "max_temp": daily["temperature_2m_max"][i],
            "min_temp": daily["temperature_2m_min"][i],
            "rain": daily["precipitation_sum"][i]
        })

    return {
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "forecast": result
    }