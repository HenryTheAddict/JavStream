#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Passenger WSGI configuration for shared hosting deployment
"""

import sys
import os

# Add the application directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask application
from app import app

# Make the application available for Passenger
application = app

# Optional: Add error handling for production
if __name__ == "__main__":
    # This will only run when executed directly, not through Passenger
    app.run(debug=False)
