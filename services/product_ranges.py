"""Product-specific temperature and humidity ranges for cold chain monitoring."""

from typing import Dict, Tuple, Optional

# Temperature and humidity ranges for fruits and vegetables
# Format: (min_temp, max_temp, min_humidity, max_humidity)
PRODUCT_RANGES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "apple": {
        "temperature": (-1.0, 4.0),  # °C - Optimal: 0-3°C
        "humidity": (90.0, 95.0),     # % - Optimal: 90-95%
    },
    "banana": {
        "temperature": (13.0, 15.0),  # °C - Tropical fruit, cold sensitive
        "humidity": (85.0, 95.0),     # % - Optimal: 90-95%
    },
    "tomato": {
        "temperature": (10.0, 13.0),  # °C - Avoid below 10°C
        "humidity": (85.0, 95.0),     # % - Optimal: 90-95%
    },
    "mango": {
        "temperature": (10.0, 13.0),  # °C - Tropical fruit
        "humidity": (85.0, 90.0),     # % - Optimal: 85-90%
    },
    "potato": {
        "temperature": (3.0, 10.0),   # °C - Avoid cold stress below 3°C
        "humidity": (85.0, 95.0),     # % - Optimal: 90-95%
    },
    "carrot": {
        "temperature": (0.0, 5.0),    # °C - Optimal: 0-2°C
        "humidity": (90.0, 99.0),     # % - High humidity needed
    },
    "onion": {
        "temperature": (0.0, 5.0),    # °C - Cool and dry
        "humidity": (65.0, 75.0),     # % - Lower humidity than most
    },
    "lettuce": {
        "temperature": (0.0, 2.0),    # °C - Very cold sensitive
        "humidity": (95.0, 100.0),    # % - Very high humidity needed
    },
    "strawberry": {
        "temperature": (0.0, 2.0),    # °C - Highly perishable
        "humidity": (90.0, 95.0),     # % - Optimal: 90-95%
    },
    "orange": {
        "temperature": (3.0, 9.0),    # °C - Citrus optimal range
        "humidity": (85.0, 90.0),     # % - Optimal: 85-90%
    },
    "grape": {
        "temperature": (-1.0, 2.0),   # °C - Can tolerate slight freezing
        "humidity": (90.0, 95.0),     # % - Optimal: 90-95%
    },
    "broccoli": {
        "temperature": (0.0, 2.0),    # °C - Very cold sensitive
        "humidity": (95.0, 100.0),    # % - Very high humidity needed
    },
    "cucumber": {
        "temperature": (10.0, 13.0),  # °C - Avoid chilling injury
        "humidity": (90.0, 95.0),     # % - Optimal: 90-95%
    },
    "cabbage": {
        "temperature": (0.0, 5.0),    # °C - Optimal: 0-2°C
        "humidity": (90.0, 98.0),     # % - High humidity needed
    },
    "spinach": {
        "temperature": (0.0, 2.0),    # °C - Highly perishable
        "humidity": (95.0, 100.0),    # % - Very high humidity needed
    },
}


def get_product_range(product_type: str) -> Optional[Dict[str, Tuple[float, float]]]:
    """
    Get temperature and humidity ranges for a specific product.
    
    Args:
        product_type: Product name (case-insensitive)
        
    Returns:
        Dictionary with 'temperature' and 'humidity' ranges, or None if not found
    """
    return PRODUCT_RANGES.get(product_type.lower().strip())


def is_temperature_in_range(product_type: str, temperature: float) -> bool:
    """
    Check if temperature is within acceptable range for a product.
    
    Args:
        product_type: Product name
        temperature: Temperature in Celsius
        
    Returns:
        True if in range, False otherwise
    """
    ranges = get_product_range(product_type)
    if not ranges:
        return True  # If product not found, assume it's okay
    
    min_temp, max_temp = ranges["temperature"]
    return min_temp <= temperature <= max_temp


def is_humidity_in_range(product_type: str, humidity: float) -> bool:
    """
    Check if humidity is within acceptable range for a product.
    
    Args:
        product_type: Product name
        humidity: Humidity percentage (0-100)
        
    Returns:
        True if in range, False otherwise
    """
    ranges = get_product_range(product_type)
    if not ranges:
        return True  # If product not found, assume it's okay
    
    min_humidity, max_humidity = ranges["humidity"]
    return min_humidity <= humidity <= max_humidity


def check_conditions(product_type: str, temperature: float, humidity: float) -> Dict[str, any]:
    """
    Check if both temperature and humidity are within acceptable ranges.
    
    Args:
        product_type: Product name
        temperature: Temperature in Celsius
        humidity: Humidity percentage (0-100)
        
    Returns:
        Dictionary with check results and details
    """
    ranges = get_product_range(product_type)
    
    if not ranges:
        return {
            "product_found": False,
            "temperature_ok": True,
            "humidity_ok": True,
            "violations": []
        }
    
    min_temp, max_temp = ranges["temperature"]
    min_humidity, max_humidity = ranges["humidity"]
    
    temp_ok = min_temp <= temperature <= max_temp
    humidity_ok = min_humidity <= humidity <= max_humidity
    
    violations = []
    if not temp_ok:
        if temperature < min_temp:
            violations.append(f"Temperature {temperature}°C is below minimum {min_temp}°C")
        else:
            violations.append(f"Temperature {temperature}°C exceeds maximum {max_temp}°C")
    
    if not humidity_ok:
        if humidity < min_humidity:
            violations.append(f"Humidity {humidity}% is below minimum {min_humidity}%")
        else:
            violations.append(f"Humidity {humidity}% exceeds maximum {max_humidity}%")
    
    return {
        "product_found": True,
        "product_type": product_type,
        "temperature_ok": temp_ok,
        "humidity_ok": humidity_ok,
        "violations": violations,
        "ranges": {
            "temperature": {"min": min_temp, "max": max_temp},
            "humidity": {"min": min_humidity, "max": max_humidity}
        }
    }
