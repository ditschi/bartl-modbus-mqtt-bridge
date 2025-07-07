#!/usr/bin/env python3
"""
MQTT Auto Discovery Publisher for Home Assistant

This script publishes Home Assistant MQTT Auto Discovery configurations
to your MQTT broker.

Usage:
    python publish_discovery.py --config ha_discovery_correct.json --mqtt-host your-mqtt-host --mqtt-user your-user --mqtt-password your-password

Features:
- Publishes all discovery configurations from JSON file
- Supports authentication
- Sets retain flag for discovery messages
- Shows progress and confirmation
"""

import json
import argparse
import sys
from pathlib import Path

def publish_discovery_configs(config_file: str, mqtt_host: str, mqtt_port: int = 1883, 
                            mqtt_user: str = None, mqtt_password: str = None):
    """Publish discovery configurations to MQTT broker"""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("paho-mqtt not installed. Install with: pip install paho-mqtt")
        return False
    
    # Load discovery configurations
    with open(config_file, 'r', encoding='utf-8') as f:
        discovery_configs = json.load(f)
    
    print(f"Loaded {len(discovery_configs)} discovery configurations from {config_file}")
    
    client = mqtt.Client()
    
    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)
        print(f"Connecting to {mqtt_host}:{mqtt_port} as {mqtt_user}")
    else:
        print(f"Connecting to {mqtt_host}:{mqtt_port} (no authentication)")
    
    try:
        client.connect(mqtt_host, mqtt_port, 60)
        print("Connected to MQTT broker")
        
        published_count = 0
        for topic, config in discovery_configs.items():
            payload = json.dumps(config)
            result = client.publish(topic, payload, retain=True)
            if result.rc == 0:
                published_count += 1
                print(f"✓ Published: {topic}")
            else:
                print(f"✗ Failed to publish: {topic} (rc={result.rc})")
        
        client.disconnect()
        print(f"\nSuccessfully published {published_count}/{len(discovery_configs)} configurations")
        print("Home Assistant should now auto-discover your Bartl Heat Pump devices!")
        return True
        
    except Exception as e:
        print(f"Failed to publish to MQTT: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Publish Home Assistant MQTT Auto Discovery configurations')
    parser.add_argument('--config', required=True, help='Path to JSON discovery config file')
    parser.add_argument('--mqtt-host', required=True, help='MQTT broker hostname')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT broker port')
    parser.add_argument('--mqtt-user', help='MQTT username')
    parser.add_argument('--mqtt-password', help='MQTT password')
    
    args = parser.parse_args()
    
    if not Path(args.config).exists():
        print(f"Config file not found: {args.config}")
        sys.exit(1)
    
    success = publish_discovery_configs(
        args.config,
        args.mqtt_host, 
        args.mqtt_port, 
        args.mqtt_user, 
        args.mqtt_password
    )
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
