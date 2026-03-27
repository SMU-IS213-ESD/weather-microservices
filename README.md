# Weather Service

## What this microservice does

The Weather Service is an atomic microservice in the Smart Drone Delivery Platform.
It wraps the [OpenWeather Current Weather API](https://openweathermap.org/current) and adds drone-specific flight safety logic on top of the raw weather data.

It is called by two composite services:
- **Book Drone** — checks whether weather is safe before confirming a booking
- **Item Delivery** — rechecks conditions right before a drone is dispatched

Given a pair of GPS coordinates, the service:
1. Checks a Redis cache (5-minute TTL) to avoid hammering the external API
2. Fetches live weather data from OpenWeather on a cache miss
3. Evaluates the data against hard safety thresholds (wind speed, visibility, temperature, weather condition)
4. Returns a structured response containing the raw reading, a `safe` flag, and a plain-English reason for every violated threshold

The service does **not** handle authentication (that is enforced upstream) and does **not** publish or consume RabbitMQ events.

---

## Safety thresholds

| Condition | Threshold | Result if breached |
|---|---|---|
| Wind speed | > 10 m/s | Unsafe |
| Visibility | < 1 000 m | Unsafe |
| Temperature | < 0 °C or > 45 °C | Unsafe |
| Weather condition | Thunderstorm or Snow | Unsafe |
| Weather description | contains storm / heavy rain / tornado / blizzard / squall / etc. | Unsafe |

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/weather/check?lat=&lon=` | Weather data + drone safety assessment |
| GET | `/weather/current?lat=&lon=` | Raw weather data only (no safety logic) |
| GET | `/health` | Liveness probe |

### Example response — `/weather/check`

```json
{
  "lat": 1.3,
  "lon": 103.8,
  "safe": true,
  "reasons": [],
  "weather": {
    "temperature": 28.4,
    "windSpeed": 3.1,
    "visibility": 10000,
    "condition": "Clouds",
    "description": "scattered clouds"
  },
  "source": "api",
  "checkedAt": "2024-06-01T08:00:00+00:00"
}
```

When unsafe, `safe` is `false` and `reasons` lists every violated threshold:

```json
{
  "safe": false,
  "reasons": [
    "Wind speed 13.2 m/s exceeds the 10.0 m/s limit",
    "Visibility 400 m is below the 1000 m minimum"
  ]
}
```

---

## Project structure

```
app/
├── main.py                        FastAPI app entry point
├── config/constants.py            Safety thresholds and cache settings
├── models/weather_models.py       Pydantic response models
├── services/
│   ├── weather_service.py         OpenWeather API client
│   ├── safety_service.py          Flight safety evaluation logic
│   └── cache_service.py           Redis get/set helpers
├── controllers/weather_controller.py  Orchestrates cache, fetch, and safety
├── routes/weather.py              Route definitions
└── middleware/error_handler.py    Global exception → JSON error mapping
tests/
└── test_weather.py                Unit tests (OpenWeather and Redis fully mocked)
Dockerfile
docker-compose.yml
.env.example
requirements.txt
```

---

## Quickstart

### 1. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your OpenWeather API key:

```
OPENWEATHER_API_KEY=your_api_key_here
REDIS_HOST=localhost
REDIS_PORT=6379
PORT=8006
```

Get a free API key at <https://openweathermap.org/api>.

### 2. Start with Docker Compose (recommended)

```bash
docker compose up --build
```

This starts the `web` service on port **8006** and a `redis:7-alpine` container.

### 3. Start without Docker (local development)

```bash
pip install -r requirements.txt
python app/main.py
```

---

## How to verify the service is working

### Liveness check

```bash
curl http://localhost:8006/health
```

Expected response:

```json
{"status": "ok"}
```

### Safety check (replace coordinates with your target location)

```bash
curl "http://localhost:8006/weather/check?lat=1.3&lon=103.8"
```

Expected: HTTP 200 with a JSON body containing `safe`, `reasons`, `weather`, `source`, and `checkedAt`.

### Raw weather data

```bash
curl "http://localhost:8006/weather/current?lat=1.3&lon=103.8"
```

Expected: HTTP 200 with `weather` fields and no safety keys.

### Verify caching is working

Run the same request twice and check that the second response has `"source": "cache"`:

```bash
curl "http://localhost:8006/weather/check?lat=1.3&lon=103.8" | python -m json.tool
# wait a moment, then:
curl "http://localhost:8006/weather/check?lat=1.3&lon=103.8" | python -m json.tool
```

The second response should show `"source": "cache"`.

### Testing with Postman

**1. Health check**

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8006/health` |

Expected response:
```json
{"status": "ok"}
```

---

**2. Safety check — `GET /weather/check`**

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8006/weather/check` |

In the **Params** tab, add:

| Key | Value |
|---|---|
| `lat` | `1.3` |
| `lon` | `103.8` |

Expected: HTTP `200` with `safe`, `reasons`, `weather`, `source`, and `checkedAt` in the response body.

To test an unsafe scenario, use coordinates for a known storm region or temporarily lower the thresholds in [app/config/constants.py](app/config/constants.py).

---

**3. Raw weather — `GET /weather/current`**

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8006/weather/current` |

In the **Params** tab, add:

| Key | Value |
|---|---|
| `lat` | `1.3` |
| `lon` | `103.8` |

Expected: HTTP `200` with `weather` and `fetchedAt` — no `safe` or `reasons` fields.

---

**4. Verify caching**

Send the same `/weather/check` request twice. The first response will have `"source": "api"`. The second (within 5 minutes) will have `"source": "cache"`, confirming Redis is working.

---

**Common Postman errors**

| Response | Cause | Fix |
|---|---|---|
| `502` `upstream_api_error` with cod 401 | Invalid or inactive API key | Check `.env` has the correct key; new keys can take up to 2 hours to activate |
| `503` `upstream_unavailable` | Cannot reach OpenWeather | Check your internet connection |
| `422 Unprocessable Entity` | Missing or out-of-range `lat`/`lon` | Ensure both params are present and within valid ranges |
| Connection refused | Service not running | Run `docker compose up --build` first |

---

### Interactive API docs (Swagger UI)

Open in a browser:

```
http://localhost:8006/docs
```

You can test both endpoints directly from the browser without needing curl.

### Run the unit tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All tests mock the OpenWeather API and Redis — no live services required.

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENWEATHER_API_KEY` | Yes | — | API key from openweathermap.org |
| `REDIS_HOST` | No | `localhost` | Redis hostname |
| `REDIS_PORT` | No | `6379` | Redis port |
| `PORT` | No | `8006` | Port the service listens on |
