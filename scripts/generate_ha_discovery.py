#!/usr/bin/env python3
"""
MQTT Auto Discovery Generator for modbus4mqtt configurations

This script reads a modbus4mqtt YAML configuration file and generates
Home Assistant MQTT Auto Discovery configuration messages.

Usage:
    python generate_ha_discovery.py --config path/to/config.yml --mqtt-prefix bartl_wp --output discovery.json

Features:
- Automatically maps modbus4mqtt topics to HA discovery topics
- Handles value mappings for select entities
- Supports different entity types (sensor, number, select, switch)
- Groups entities by device based on topic structure
"""

import yaml
import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional


class HADiscoveryGenerator:
    def __init__(self, mqtt_prefix: str = ""):
        self.mqtt_prefix = mqtt_prefix
        self.devices = {}
        self.discovery_configs = {}
        
        # Mapping for common device classes
        self.device_class_mapping = {
            'temperatur': 'temperature',
            'temperature': 'temperature',
            'feuchte': 'humidity',
            'humidity': 'humidity',
            'druck': 'pressure',
            'pressure': 'pressure',
            'leistung': 'power',
            'power': 'power',
            'energie': 'energy',
            'energy': 'energy',
            'spannung': 'voltage',
            'voltage': 'voltage',
            'strom': 'current',
            'current': 'current'
        }
        
        # Unit mapping
        self.unit_mapping = {
            'temperatur': '°C',
            'temperature': '°C',
            '°c': '°C',
            'celsius': '°C',
            'grad': '°C',
            'feuchte': '%',
            'humidity': '%',
            '%': '%',
            'prozent': '%',
            'percent': '%',
            'kw': 'kW',
            'kilowatt': 'kW',
            'w': 'W',
            'watt': 'W',
            'leistung': 'W',
            'power': 'W',
            'kwh': 'kWh',
            'wh': 'Wh',
            'energie': 'kWh',
            'energy': 'kWh',
            'verbrauch': 'kWh',
            'v': 'V',
            'volt': 'V',
            'spannung': 'V',
            'voltage': 'V',
            'a': 'A',
            'ampere': 'A',
            'strom': 'A',
            'current': 'A',
            'bar': 'bar',
            'druck': 'bar',
            'pressure': 'bar',
            'h': 'h',
            'stunden': 'h',
            'hours': 'h',
            'min': 'min',
            'minuten': 'min',
            'minutes': 'min',
            's': 's',
            'sekunden': 's',
            'seconds': 's'
        }

    def extract_device_info(self, topic: str) -> Dict[str, Any]:
        """Extract device information from topic structure"""
        parts = topic.split('/')
        if not parts:
            return {"identifiers": ["unknown"], "name": "Unknown Device"}
            
        device_id = parts[0]
        device_name = device_id.replace('_', ' ').title()
        
        return {
            "identifiers": [device_id],
            "name": f"Bartl WP - {device_name}",
            "manufacturer": "Bartl",
            "model": "Heat Pump Controller",
            "sw_version": "1.0"
        }

    def determine_entity_type(self, register: Dict[str, Any]) -> str:
        """Determine the Home Assistant entity type based on register configuration"""
        # Check if it has value mappings - likely a select
        if 'value_map' in register and register['value_map']:
            # If it also has set_topic, it's a controllable select
            if 'set_topic' in register:
                return 'select'
            else:
                return 'sensor'  # Read-only sensor with state mapping
        
        # Check if it has set_topic - likely a number input
        if 'set_topic' in register:
            # Check if it looks like a binary switch
            topic_lower = register.get('pub_topic', '').lower()
            if any(word in topic_lower for word in ['pumpe', 'pump', 'schalter', 'switch', 'aktiv', 'enable']):
                return 'switch'
            return 'number'
        
        # Default to sensor for read-only values
        return 'sensor'

    def get_device_class(self, register: Dict[str, Any]) -> Optional[str]:
        """Determine device class from register information"""
        topic = register.get('pub_topic', '').lower()
        
        # Check topic for device class hints
        for key, device_class in self.device_class_mapping.items():
            if key in topic:
                return device_class
        
        return None

    def get_unit_of_measurement(self, register: Dict[str, Any]) -> Optional[str]:
        """Extract unit of measurement from register or topic"""
        topic = register.get('pub_topic', '').lower()
        
        # Check topic for unit hints
        for unit_hint, standard_unit in self.unit_mapping.items():
            if unit_hint in topic:
                return standard_unit
        
        return None

    def create_sensor_config(self, register: Dict[str, Any], device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create sensor configuration"""
        topic = register['pub_topic']
        name = self.generate_friendly_name(topic)
        unique_id = topic.replace('/', '_')
        
        config = {
            "device": device_info,
            "name": name,
            "state_topic": f"{self.mqtt_prefix}/{topic}" if self.mqtt_prefix else topic,
            "unique_id": unique_id
        }
        
        # Add device class if detected
        device_class = self.get_device_class(register)
        if device_class:
            config["device_class"] = device_class
        
        # Add unit of measurement
        unit = self.get_unit_of_measurement(register)
        if unit:
            config["unit_of_measurement"] = unit
        
        # Add state class for numeric sensors
        if device_class in ['temperature', 'humidity', 'power', 'energy', 'voltage', 'current']:
            if 'betriebsstunden' in topic.lower() or 'verbrauch' in topic.lower():
                config["state_class"] = "total_increasing"
            else:
                config["state_class"] = "measurement"
        
        # Add value template for mapped values
        if 'value_map' in register and register['value_map']:
            value_map = register['value_map']
            template_conditions = []
            for state, value in value_map.items():
                template_conditions.append(f"value == '{value}' %}}{state}")
            
            config["value_template"] = "{% if " + "{% elif ".join(template_conditions) + "{% else %}{{ value }}{% endif %}"
        
        # Add scaling if present
        if 'scale' in register and register['scale'] != 1:
            if 'value_template' not in config:
                config["value_template"] = f"{{{{ (value | float) * {register['scale']} }}}}"
        
        return config

    def create_number_config(self, register: Dict[str, Any], device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create number input configuration"""
        topic = register['pub_topic']
        name = self.generate_friendly_name(topic)
        unique_id = topic.replace('/', '_')
        
        config = {
            "device": device_info,
            "name": name,
            "state_topic": f"{self.mqtt_prefix}/{topic}" if self.mqtt_prefix else topic,
            "command_topic": f"{self.mqtt_prefix}/{register['set_topic']}" if self.mqtt_prefix else register['set_topic'],
            "unique_id": unique_id
        }
        
        # Add unit of measurement
        unit = self.get_unit_of_measurement(register)
        if unit:
            config["unit_of_measurement"] = unit
        
        # Set reasonable min/max based on unit and topic
        if unit == '°C':
            if 'raumtemperatur' in topic.lower():
                config["min"] = 5
                config["max"] = 35
                config["step"] = 0.5
            else:
                config["min"] = -20
                config["max"] = 100
                config["step"] = 0.1
        elif unit == '%':
            config["min"] = 0
            config["max"] = 100
            config["step"] = 1
        elif unit in ['kW', 'W']:
            config["min"] = 0
            config["max"] = 50
            config["step"] = 0.1
        
        # Add scaling if present
        if 'scale' in register and register['scale'] != 1:
            config["value_template"] = f"{{{{ (value | float) * {register['scale']} }}}}"
            # For command, we need to reverse the scaling
            config["command_template"] = f"{{{{ (value | float) / {register['scale']} }}}}"
        
        return config

    def create_select_config(self, register: Dict[str, Any], device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create select configuration"""
        topic = register['pub_topic']
        name = self.generate_friendly_name(topic)
        unique_id = topic.replace('/', '_')
        
        config = {
            "device": device_info,
            "name": name,
            "state_topic": f"{self.mqtt_prefix}/{topic}" if self.mqtt_prefix else topic,
            "unique_id": unique_id
        }
        
        if 'set_topic' in register:
            config["command_topic"] = f"{self.mqtt_prefix}/{register['set_topic']}" if self.mqtt_prefix else register['set_topic']
        
        # Add options from value_map
        if 'value_map' in register and register['value_map']:
            config["options"] = list(register['value_map'].keys())
            
            # Create value template to map numbers to text
            value_map = register['value_map']
            template_conditions = []
            for state, value in value_map.items():
                template_conditions.append(f"value == '{value}' %}}{state}")
            
            config["value_template"] = "{% if " + "{% elif ".join(template_conditions) + "{% else %}{{ value }}{% endif %}"
            
            # Create command template to map text to numbers
            command_conditions = []
            for state, value in value_map.items():
                command_conditions.append(f"value == '{state}' %}}{value}")
            
            config["command_template"] = "{% if " + "{% elif ".join(command_conditions) + "{% else %}{{ value }}{% endif %}"
        
        return config

    def create_switch_config(self, register: Dict[str, Any], device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create switch configuration"""
        topic = register['pub_topic']
        name = self.generate_friendly_name(topic)
        unique_id = topic.replace('/', '_')
        
        config = {
            "device": device_info,
            "name": name,
            "state_topic": f"{self.mqtt_prefix}/{topic}" if self.mqtt_prefix else topic,
            "command_topic": f"{self.mqtt_prefix}/{register['set_topic']}" if self.mqtt_prefix else register['set_topic'],
            "payload_on": "1",
            "payload_off": "0",
            "state_on": "1",
            "state_off": "0",
            "unique_id": unique_id
        }
        
        return config

    def generate_friendly_name(self, topic: str) -> str:
        """Generate a user-friendly name from topic"""
        # Remove common prefixes and clean up the topic
        parts = topic.split('/')
        
        # Create a readable name
        name_parts = []
        for part in parts:
            # Replace underscores and clean up
            clean_part = part.replace('_', ' ')
            # Capitalize each word
            clean_part = ' '.join(word.capitalize() for word in clean_part.split())
            name_parts.append(clean_part)
        
        return ' '.join(name_parts)

    def generate_discovery_configs(self, config_file: str) -> Dict[str, Any]:
        """Generate discovery configurations from modbus4mqtt config"""
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if 'registers' not in config:
            raise ValueError("No 'registers' section found in config file")
        
        discovery_configs = {}
        
        for register in config['registers']:
            if 'pub_topic' not in register:
                continue
            
            topic = register['pub_topic']
            device_info = self.extract_device_info(topic)
            entity_type = self.determine_entity_type(register)
            
            # Generate unique_id and discovery topic
            unique_id = topic.replace('/', '_')
            discovery_topic = f"homeassistant/{entity_type}/{unique_id}/config"
            
            # Create configuration based on entity type
            if entity_type == 'sensor':
                entity_config = self.create_sensor_config(register, device_info)
            elif entity_type == 'number':
                entity_config = self.create_number_config(register, device_info)
            elif entity_type == 'select':
                entity_config = self.create_select_config(register, device_info)
            elif entity_type == 'switch':
                entity_config = self.create_switch_config(register, device_info)
            else:
                continue
            
            discovery_configs[discovery_topic] = entity_config
        
        return discovery_configs

    def save_discovery_configs(self, discovery_configs: Dict[str, Any], output_file: str):
        """Save discovery configurations to JSON file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(discovery_configs, f, indent=2, ensure_ascii=False)

    def publish_discovery_configs(self, discovery_configs: Dict[str, Any], mqtt_host: str, 
                                mqtt_port: int = 1883, mqtt_user: str = None, mqtt_password: str = None):
        """Publish discovery configurations to MQTT broker"""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("paho-mqtt not installed. Install with: pip install paho-mqtt")
            return False
        
        client = mqtt.Client()
        
        if mqtt_user and mqtt_password:
            client.username_pw_set(mqtt_user, mqtt_password)
        
        try:
            client.connect(mqtt_host, mqtt_port, 60)
            
            for topic, config in discovery_configs.items():
                payload = json.dumps(config)
                client.publish(topic, payload, retain=True)
                print(f"Published: {topic}")
            
            client.disconnect()
            return True
        except Exception as e:
            print(f"Failed to publish to MQTT: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Generate Home Assistant MQTT Auto Discovery from modbus4mqtt config')
    parser.add_argument('--config', required=True, help='Path to modbus4mqtt YAML config file')
    parser.add_argument('--mqtt-prefix', default='', help='MQTT topic prefix used by modbus4mqtt')
    parser.add_argument('--output', default='ha_discovery.json', help='Output JSON file for discovery configs')
    parser.add_argument('--publish', action='store_true', help='Publish directly to MQTT broker')
    parser.add_argument('--mqtt-host', help='MQTT broker hostname')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT broker port')
    parser.add_argument('--mqtt-user', help='MQTT username')
    parser.add_argument('--mqtt-password', help='MQTT password')
    
    args = parser.parse_args()
    
    if not Path(args.config).exists():
        print(f"Config file not found: {args.config}")
        sys.exit(1)
    
    # Generate discovery configurations
    generator = HADiscoveryGenerator(args.mqtt_prefix)
    
    try:
        discovery_configs = generator.generate_discovery_configs(args.config)
        print(f"Generated {len(discovery_configs)} discovery configurations")
        
        # Save to file
        generator.save_discovery_configs(discovery_configs, args.output)
        print(f"Saved discovery configurations to: {args.output}")
        
        # Optionally publish to MQTT
        if args.publish:
            if not args.mqtt_host:
                print("--mqtt-host required when using --publish")
                sys.exit(1)
            
            success = generator.publish_discovery_configs(
                discovery_configs, 
                args.mqtt_host, 
                args.mqtt_port, 
                args.mqtt_user, 
                args.mqtt_password
            )
            
            if success:
                print("Successfully published all discovery configurations to MQTT")
            else:
                print("Failed to publish to MQTT")
                sys.exit(1)
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
