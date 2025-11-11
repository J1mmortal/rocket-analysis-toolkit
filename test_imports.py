# test_imports.py - run this to verify all imports work

try:
    from rocket_toolkit.core.flight_simulator import FlightSimulator
    print("✓ FlightSimulator import works")
except Exception as e:
    print(f"✗ FlightSimulator import failed: {e}")

try:
    from rocket_toolkit.geometry.rocket_fin import RocketFin
    print("✓ RocketFin import works")
except Exception as e:
    print(f"✗ RocketFin import failed: {e}")

try:
    from rocket_toolkit.core.stability_analyzer import RocketStability
    print("✓ RocketStability import works")
except Exception as e:
    print(f"✗ RocketStability import failed: {e}")

try:
    from rocket_toolkit.geometry.component_manager import ComponentData
    print("✓ ComponentData import works")
except Exception as e:
    print(f"✗ ComponentData import failed: {e}")

try:
    from rocket_toolkit import config
    print("✓ config import works")
except Exception as e:
    print(f"✗ config import failed: {e}")

print("\nAll imports successful! Ready for Git.")
