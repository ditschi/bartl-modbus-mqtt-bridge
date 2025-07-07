#!/usr/bin/env python3
"""
MQTT Discovery Cleanup Tool

This script removes Home Assistant MQTT Auto Discovery configurations
by publishing empty messages to discovery topics, effectively removing
the entities from Home Assistant.

Usage:
    python cleanup_discovery.py --config ha_discovery.json --mqtt-host your-mqtt-host
    python cleanup_discovery.py --discovery-prefix homeassistant --device-prefix bartl_wp --mqtt-host your-mqtt-host

Features:
- Remove discovery configs from JSON file
- Remove all discovery topics with specific prefix
- Dry-run mode to see what would be removed
- Confirmation prompts for safety
"""

import json
import argparse
import sys
from pathlib import Path
import time

def cleanup_from_json(config_file: str, mqtt_host: str, mqtt_port: int = 1883,
                     mqtt_user: str = None, mqtt_password: str = None, dry_run: bool = False):
    """Remove discovery configurations from JSON file"""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("❌ paho-mqtt not installed. Install with: pip install paho-mqtt")
        return False

    if not Path(config_file).exists():
        print(f"❌ Config file not found: {config_file}")
        return False

    # Load discovery configurations
    with open(config_file, 'r', encoding='utf-8') as f:
        discovery_configs = json.load(f)

    print(f"📋 Found {len(discovery_configs)} discovery configurations in {config_file}")

    if dry_run:
        print("🔍 DRY RUN - No changes will be made")
        print("\nTopics that would be removed:")
        for topic in discovery_configs.keys():
            print(f"  - {topic}")
        return True

    # Ask for confirmation
    print(f"\n⚠️  This will remove {len(discovery_configs)} entities from Home Assistant!")
    print("The entities will disappear from your dashboard and you'll lose their history.")

    response = input("\nAre you sure you want to continue? Type 'yes' to confirm: ")
    if response.lower() != 'yes':
        print("❌ Operation cancelled")
        return False

    print(f"🔗 Connecting to MQTT broker at {mqtt_host}:{mqtt_port}")

    client = mqtt.Client()

    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)

    try:
        client.connect(mqtt_host, mqtt_port, 60)
        print("✅ Connected to MQTT broker")

        removed_count = 0
        for topic in discovery_configs.keys():
            # Publish empty message with retain=True to remove the topic
            result = client.publish(topic, "", retain=True)
            if result.rc == 0:
                removed_count += 1
                print(f"🗑️  Removed: {topic}")
            else:
                print(f"❌ Failed to remove: {topic} (rc={result.rc})")

            # Small delay to avoid overwhelming the broker
            time.sleep(0.1)

        client.disconnect()
        print(f"\n✅ Successfully removed {removed_count}/{len(discovery_configs)} discovery topics")
        print("🏠 Home Assistant should remove the entities within a few minutes")
        return True

    except Exception as e:
        print(f"❌ Failed to connect to MQTT broker: {e}")
        return False


def cleanup_by_prefix(discovery_prefix: str, device_prefix: str = None, mqtt_host: str = None,
                     mqtt_port: int = 1883, mqtt_user: str = None, mqtt_password: str = None,
                     dry_run: bool = False):
    """Remove all discovery topics matching prefixes"""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("❌ paho-mqtt not installed. Install with: pip install paho-mqtt")
        return False

    # Build the topic patterns to search for
    entity_types = ['sensor', 'number', 'select', 'switch', 'binary_sensor', 'button']
    topics_to_remove = []

    if device_prefix:
        # Generate specific topics for the device prefix
        for entity_type in entity_types:
            # Pattern: homeassistant/sensor/device_name_entity_name/config
            topics_to_remove.append(f"{discovery_prefix}/{entity_type}/{device_prefix}_*/config")
            topics_to_remove.append(f"{discovery_prefix}/{entity_type}/{device_prefix}*/config")
    else:
        # Remove all discovery topics with the discovery prefix
        for entity_type in entity_types:
            topics_to_remove.append(f"{discovery_prefix}/{entity_type}/*/config")

    print(f"🔍 Will search for discovery topics with patterns:")
    for pattern in topics_to_remove:
        print(f"  - {pattern}")

    if dry_run:
        print("\n🔍 DRY RUN - No changes will be made")
        print("Use --mqtt-host with actual connection to see discovered topics")
        return True

    if not mqtt_host:
        print("❌ --mqtt-host required for prefix-based cleanup")
        return False

    print(f"\n⚠️  This will remove ALL discovery topics matching the patterns above!")
    print("This could remove entities you want to keep if they share the same prefix.")

    response = input("\nAre you sure you want to continue? Type 'yes' to confirm: ")
    if response.lower() != 'yes':
        print("❌ Operation cancelled")
        return False

    # For prefix-based cleanup, we need to subscribe and collect topics first
    discovered_topics = []

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT broker")
            # Subscribe to discovery topics
            for entity_type in entity_types:
                topic = f"{discovery_prefix}/{entity_type}/+/config"
                client.subscribe(topic)
                print(f"🔍 Subscribed to: {topic}")
        else:
            print(f"❌ Failed to connect to MQTT broker (rc={rc})")

    def on_message(client, userdata, msg):
        topic = msg.topic
        # Filter by device prefix if specified
        if device_prefix:
            topic_parts = topic.split('/')
            if len(topic_parts) >= 3:
                entity_id = topic_parts[2]
                if entity_id.startswith(device_prefix):
                    discovered_topics.append(topic)
        else:
            discovered_topics.append(topic)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)

    try:
        client.connect(mqtt_host, mqtt_port, 60)

        # Listen for discovery topics for a few seconds
        print("🔍 Discovering existing topics...")
        client.loop_start()
        time.sleep(5)  # Listen for 5 seconds
        client.loop_stop()

        if not discovered_topics:
            print("ℹ️  No matching discovery topics found")
            return True

        print(f"\n📋 Found {len(discovered_topics)} matching topics:")
        for topic in discovered_topics:
            print(f"  - {topic}")

        print(f"\n⚠️  About to remove {len(discovered_topics)} discovery topics!")
        response = input("Continue? Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("❌ Operation cancelled")
            return False

        # Remove the discovered topics
        removed_count = 0
        for topic in discovered_topics:
            result = client.publish(topic, "", retain=True)
            if result.rc == 0:
                removed_count += 1
                print(f"🗑️  Removed: {topic}")
            else:
                print(f"❌ Failed to remove: {topic} (rc={result.rc})")
            time.sleep(0.1)

        client.disconnect()
        print(f"\n✅ Successfully removed {removed_count}/{len(discovered_topics)} discovery topics")
        print("🏠 Home Assistant should remove the entities within a few minutes")
        return True

    except Exception as e:
        print(f"❌ Failed to connect to MQTT broker: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Remove Home Assistant MQTT Auto Discovery configurations')

    # Input method selection
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--config', help='Path to JSON discovery config file to remove')
    input_group.add_argument('--discovery-prefix', help='Discovery prefix to search for (e.g., homeassistant)')

    # MQTT connection
    parser.add_argument('--mqtt-host', help='MQTT broker hostname')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT broker port')
    parser.add_argument('--mqtt-user', help='MQTT username')
    parser.add_argument('--mqtt-password', help='MQTT password')

    # Filtering (for prefix mode)
    parser.add_argument('--device-prefix', help='Device prefix to filter by (e.g., bartl_wp)')

    # Safety
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without actually doing it')

    args = parser.parse_args()

    print("🧹 Home Assistant MQTT Discovery Cleanup Tool")
    print("=" * 50)

    if args.config:
        # JSON file mode
        if not args.mqtt_host and not args.dry_run:
            print("❌ --mqtt-host required when removing from config file (unless using --dry-run)")
            sys.exit(1)

        success = cleanup_from_json(
            args.config,
            args.mqtt_host,
            args.mqtt_port,
            args.mqtt_user,
            args.mqtt_password,
            args.dry_run
        )
    else:
        # Prefix mode
        success = cleanup_by_prefix(
            args.discovery_prefix,
            args.device_prefix,
            args.mqtt_host,
            args.mqtt_port,
            args.mqtt_user,
            args.mqtt_password,
            args.dry_run
        )

    if not success:
        sys.exit(1)

    if not args.dry_run:
        print("\n💡 Tip: You can regenerate discovery configs with:")
        print("   python3 scripts/generate_ha_discovery.py --config config/modbus4mqtt/Bartl-WP.yml --mqtt-prefix bartl_wp")


if __name__ == '__main__':
    main()
