#!/usr/bin/env python3

from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
import json
import yaml

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException


INVENTORY_FILE = "inventory.yml"
REPORT_DIR = Path("reports")


def load_inventory(path):
    """Load router inventory from a YAML file."""
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict) or "routers" not in data:
        raise ValueError("inventory.yml must contain a 'routers' list.")

    return data["routers"]


def build_device_params(router, password):
    """Build the dictionary required by Netmiko ConnectHandler."""
    required_fields = ["device_type", "host", "username"]

    missing_fields = [
        field for field in required_fields
        if field not in router or not router[field]
    ]

    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    return {
        "device_type": router["device_type"],
        "host": router["host"],
        "username": router["username"],
        "password": password,
        "port": router.get("port", 22),
    }


def collect_router_data(router, password):
    """Connect to one router and collect show command output."""
    device_params = build_device_params(router, password)
    commands = router.get("commands", ["show ip interface brief"])

    result = {
        "device_name": router.get("name", router["host"]),
        "host": router["host"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status": "unknown",
        "commands": {}
    }

    connection = None

    try:
        connection = ConnectHandler(**device_params)
        result["prompt"] = connection.find_prompt()

        for command in commands:
            output = connection.send_command(command)
            result["commands"][command] = output

        result["status"] = "success"

    except NetmikoAuthenticationException as error:
        result["status"] = "failed"
        result["error"] = f"Authentication failed: {error}"

    except NetmikoTimeoutException as error:
        result["status"] = "failed"
        result["error"] = f"Connection timed out: {error}"

    finally:
        if connection:
            connection.disconnect()

    return result


def save_report(result):
    """Save collected router data as JSON."""
    REPORT_DIR.mkdir(exist_ok=True)

    filename = f"{result['device_name']}.json"
    output_path = REPORT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    return output_path


def main():
    routers = load_inventory(INVENTORY_FILE)
    password = getpass("Router SSH password: ")

    for router in routers:
        print(f"Collecting data from {router.get('name', router['host'])}...")

        result = collect_router_data(router, password)
        report_path = save_report(result)

        print(f"Status: {result['status']}")
        print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()