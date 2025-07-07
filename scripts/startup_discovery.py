#!/usr/bin/env python3
"""
Startup script for MQTT Auto Discovery in Docker environment

This script waits for modbus4mqtt and MQTT broker to be ready,
then generates and publishes Home Assistant MQTT Auto Discovery configurations.
"""

import os
import time
import sys
import subprocess
import json
from pathlib import Path

def wait_for_service(host, port, timeout=60):
    """Wait for a service to be available"""
    import socket
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(2)
    return False

def main():
    print("🚀 Starting MQTT Auto Discovery setup...")
    
    # Configuration from environment variables
    config_file = os.getenv('CONFIG_FILE', 'config/modbus4mqtt/Bartl-WP.yml')
    mqtt_prefix = os.getenv('MQTT_PREFIX', 'bartl_wp')
    discovery_prefix = os.getenv('DISCOVERY_PREFIX', 'homeassistant')
    mqtt_host = os.getenv('MQTT_SERVER_ADDRESS')
    mqtt_port = int(os.getenv('MQTT_SERVER_PORT', '1883'))
    mqtt_user = os.getenv('MQTT_SERVER_USER')
    mqtt_password = os.getenv('MQTT_SERVER_PASSWORD')
    output_file = os.getenv('OUTPUT_FILE', 'ha_discovery.json')
    
    if not mqtt_host:
        print("❌ MQTT_SERVER_ADDRESS environment variable is required")
        sys.exit(1)
    
    print(f"📋 Configuration:")
    print(f"   Config file: {config_file}")
    print(f"   MQTT prefix: '{mqtt_prefix}' (topics will be: {mqtt_prefix}/sensor/data)")
    print(f"   Discovery prefix: '{discovery_prefix}' (discovery topics: {discovery_prefix}/sensor/...)")
    print(f"   MQTT broker: {mqtt_host}:{mqtt_port}")
    print(f"   Output file: {output_file}")
    
    # Wait for MQTT broker to be available
    print(f"⏳ Waiting for MQTT broker at {mqtt_host}:{mqtt_port}...")
    if not wait_for_service(mqtt_host, mqtt_port, timeout=120):
        print(f"❌ MQTT broker at {mqtt_host}:{mqtt_port} is not available after 120 seconds")
        sys.exit(1)
    print("✅ MQTT broker is available")
    
    # Wait a bit more for modbus4mqtt to start publishing
    print("⏳ Waiting for modbus4mqtt to initialize...")
    time.sleep(30)
    
    # Generate discovery configurations
    print("🔧 Generating Home Assistant MQTT Auto Discovery configurations...")
    try:
        cmd = [
            'python3', 'scripts/generate_ha_discovery.py',
            '--config', config_file,
            '--mqtt-prefix', mqtt_prefix,
            '--discovery-prefix', discovery_prefix,
            '--output', output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Discovery configurations generated successfully")
        print(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate discovery configurations: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)
    
    # Install paho-mqtt if needed for publishing
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("📦 Installing paho-mqtt...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'paho-mqtt'], check=True)
        import paho.mqtt.client as mqtt
    
    # Publish discovery configurations
    print("📡 Publishing discovery configurations to MQTT...")
    try:
        with open(output_file, 'r') as f:
            discovery_configs = json.load(f)
        
        client = mqtt.Client()
        if mqtt_user and mqtt_password:
            client.username_pw_set(mqtt_user, mqtt_password)
        
        client.connect(mqtt_host, mqtt_port, 60)
        
        published_count = 0
        for topic, config in discovery_configs.items():
            payload = json.dumps(config)
            result = client.publish(topic, payload, retain=True)
            if result.rc == 0:
                published_count += 1
        
        client.disconnect()
        print(f"✅ Successfully published {published_count}/{len(discovery_configs)} discovery configurations")
        print("🎉 Home Assistant should now auto-discover your Bartl Heat Pump devices!")
        
    except Exception as e:
        print(f"❌ Failed to publish to MQTT: {e}")
        sys.exit(1)
    
    print("✨ MQTT Auto Discovery setup complete!")

if __name__ == '__main__':
    main()
