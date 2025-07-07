# Bartl Heat Pump Modbus-MQTT Bridge

This repository provides a complete solution for monitoring and controlling a Bartl Heat Pump system via Modbus TCP, with MQTT integration for Home Assistant and InfluxDB data logging.

## Overview

The system consists of three main components:

1. **Modbus to MQTT Bridge** - Primary component using [modbus4mqtt](https://github.com/tjhowse/modbus4mqtt) to read Modbus registers and publish to MQTT
2. **Home Assistant Auto Discovery** - Automatic generation of Home Assistant MQTT discovery configurations
3. **InfluxDB Data Logging** - Telegraf-based data collection from MQTT to InfluxDB for long-term monitoring

## Repository Structure

```
├── config/
│   ├── modbus4mqtt/
│   │   └── Bartl-WP.yml           # Modbus register configuration
│   └── telegraf/
│       └── telegraf.conf          # Telegraf configuration for InfluxDB
├── scripts/
│   ├── generate_ha_discovery.py   # HA discovery generator
│   ├── publish_discovery.py       # MQTT discovery publisher
│   ├── cleanup_discovery.py       # Remove/cleanup discovery topics
│   ├── startup_discovery.py       # Docker startup script for discovery
│   └── requirements.txt           # Python dependencies
├── docker-compose.yml             # Complete stack orchestration
├── Dockerfile.discovery           # Custom image for HA discovery
├── .env.template                  # Environment configuration template
└── README.md                      # This file
```

## Quick Start

### 1. Configuration Setup

Create your environment configuration:

```bash
cp .env.template .env
# Edit .env with your specific settings:
# - MQTT broker details
# - InfluxDB connection (if using Telegraf)
# - Modbus device IP address
```

### 2. Start the Complete Stack

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f
```

This will start:

- **modbus4mqtt** - Reads Modbus registers and publishes to MQTT
- **ha-discovery** - Generates and publishes Home Assistant discovery configs (runs once)
- **telegraf** - Collects MQTT data and sends to InfluxDB

### 3. Verify Operation

```bash
# Check modbus4mqtt is reading data
docker-compose logs modbus4mqtt

# Check MQTT topics (if you have mosquitto_sub)
mosquitto_sub -h YOUR_MQTT_HOST -u YOUR_USER -P YOUR_PASSWORD -t "bartl_wp/#"

# Check Home Assistant devices appear in Settings > Devices & Services
```

## Component Details

### 1. Modbus to MQTT Bridge (Primary Component)

The core functionality uses [modbus4mqtt](https://github.com/tjhowse/modbus4mqtt) to:

- Connect to Bartl Heat Pump via Modbus TCP (IP: 192.168.1.211:502)
- Read 100+ registers covering all heat pump functions
- Publish data to MQTT with configurable prefix (`bartl_wp`)
- Support both read-only sensors and controllable parameters

#### Configuration: `config/modbus4mqtt/Bartl-WP.yml`

Key sections:

- **Heating Circuit** (`heizkreis/*`) - Room temperature, setpoints, operating modes
- **Hot Water** (`warmwasser/*`) - Tank temperatures, operation modes, circulation
- **Buffer Tank** (`puffer/*`) - Tank temperatures, heating/cooling requests
- **Heat Pump** (`waermepumpe/*`) - Status, temperatures, operation hours, safety
- **Solar/PV** (`photovoltaik/*`) - Power thresholds, grid integration

#### MQTT Topics Structure

```text
bartl_wp/
├── status/                    # Operating modes with value mapping
│   ├── heizkreis/betriebsart
│   ├── warmwasser/betriebsart
│   └── waermepumpe/status
├── heizkreis/                 # Heating circuit
│   ├── raumtemperatur/aktuell
│   ├── temperatur/vorlauf/istwert
│   └── ...
├── warmwasser/               # Hot water system
│   ├── temperatur/oben
│   ├── temperatur/unten
│   └── ...
├── puffer/                   # Buffer tank
│   ├── istwert/temperatur_oben
│   └── ...
├── waermepumpe/             # Heat pump core
│   ├── temperatur/vorlauf
│   ├── status
│   └── ...
└── photovoltaik/            # Solar integration
    ├── einschaltschwelle_kw
    └── ...
```

### 2. Home Assistant Auto Discovery

Automatically generates Home Assistant MQTT Discovery configurations:

- **100+ entities** automatically detected from modbus config
- **Proper device grouping** by heat pump component
- **Correct entity types**: sensors, numbers, selects, switches
- **Value mapping** for status codes (0=Standby, 1=Active, etc.)
- **Units and device classes** automatically applied
- **Scaling factors** handled automatically (0.1 multipliers)

#### Generated Entity Types

- **Sensors** - Read-only values (temperatures, status, power consumption)
- **Numbers** - Adjustable numeric values (setpoints, thresholds, min/max values)
- **Selects** - Dropdown selections (operating modes, strategies)
- **Switches** - On/off controls (pumps, enable/disable functions)

### 3. InfluxDB Data Logging with Telegraf

Telegraf collects all MQTT data and stores it in InfluxDB for:

- **Long-term monitoring** and trend analysis
- **Performance optimization**
- **Energy consumption tracking**
- **Custom dashboards** in Grafana
- **Data retention** and historical analysis

#### Configuration: `config/telegraf/telegraf.conf`

- Subscribes to all `bartl_wp/*` topics
- Organizes data by device category
- Handles both numeric and text values
- Configurable InfluxDB v2 output

## Environment Configuration

The `.env` file contains all configuration for the stack.
It can be created using the available `.env.template` file:

```bash
cp .env.template .env
```

Afterwards adapt the content as needed.


## Manual Operations

### Regenerate Home Assistant Discovery

If you modify the modbus configuration:

```bash
# Regenerate discovery (using Docker)
docker-compose up ha-discovery

# Or manually with Python
python3 scripts/generate_ha_discovery.py \
    --config config/modbus4mqtt/Bartl-WP.yml \
    --mqtt-prefix $MODBUS4MQTT_TOPIC_PREFIX \
    --discovery-prefix $DISCOVERY_PREFIX \
    --output ha_discovery.json

python3 scripts/publish_discovery.py \
    --config ha_discovery.json \
    --mqtt-host $MQTT_SERVER_ADDRESS \
    --mqtt-user $MQTT_SERVER_USER \
    --mqtt-password $MQTT_SERVER_PASSWORD
```

### Clean Up Discovery Topics

If you need to remove discovery configurations (e.g., to fix issues or restructure):

```bash
# Remove all topics from a specific JSON file (safest method)
python3 scripts/cleanup_discovery.py \
    --config ha_discovery.json \
    --mqtt-host $MQTT_SERVER_ADDRESS \
    --mqtt-user $MQTT_SERVER_USER \
    --mqtt-password $MQTT_SERVER_PASSWORD

# Remove all discovery topics for a specific device prefix
python3 scripts/cleanup_discovery.py \
    --discovery-prefix homeassistant \
    --device-prefix bartl_wp \
    --mqtt-host $MQTT_SERVER_ADDRESS \
    --mqtt-user $MQTT_SERVER_USER \
    --mqtt-password $MQTT_SERVER_PASSWORD

# Dry run to see what would be removed (recommended first step)
python3 scripts/cleanup_discovery.py \
    --config ha_discovery.json \
    --dry-run
```

**Note:** Cleanup removes entities from Home Assistant. You'll lose their history and configuration. Always use `--dry-run` first!

### Monitor System

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f modbus4mqtt
docker-compose logs -f telegraf

# Check MQTT data flow
mosquitto_sub -h $MQTT_SERVER_ADDRESS -u $MQTT_SERVER_USER -P $MQTT_SERVER_PASSWORD -t "bartl_wp/#" -v

# Test Modbus connectivity
docker run --rm -it --network host alpine/socat TCP:192.168.1.211:502,connect-timeout=5
```

## Troubleshooting

### Modbus Connection Issues

- Verify heat pump IP address (192.168.1.211) is reachable
- Check network connectivity: `ping 192.168.1.211`
- Ensure Modbus TCP is enabled on heat pump
- Check firewall settings on heat pump and Docker host

### MQTT Issues

- Verify MQTT broker is accessible
- Check MQTT credentials in `.env` file
- Test MQTT connection manually
- Check modbus4mqtt logs for connection errors

### Home Assistant Discovery Issues

- Verify MQTT integration is configured in Home Assistant
- Check discovery prefix matches Home Assistant configuration
- Look for discovery messages in MQTT broker logs
- Restart Home Assistant after publishing discovery configs

### InfluxDB/Telegraf Issues

- Check Telegraf logs for InfluxDB connection errors
- Verify InfluxDB token has write permissions
- Check bucket and organization names
- Monitor InfluxDB logs for incoming data

## Data Flow Architecture

```text
Bartl Heat Pump (Modbus TCP)
           ↓
    modbus4mqtt container
           ↓
      MQTT Broker
       ↓        ↓
Home Assistant  Telegraf
   (Discovery)     ↓
                InfluxDB
                   ↓
                Grafana
```

## Security Considerations

- Use strong MQTT credentials
- Consider MQTT over TLS/SSL for production
- Secure InfluxDB token storage
- Network segmentation for industrial devices
- Regular updates of container images
