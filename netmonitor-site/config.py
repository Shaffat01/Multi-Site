import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'network-monitor-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'nodes.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # ============ POLLING SETTINGS ============
    PING_INTERVAL = 10         # 10 seconds
    PING_TIMEOUT = 1           
    PING_COUNT = 4             # 4 pings (better statistics, less false warnings)
    PING_PRIVILEGED = True     
    MAX_CONCURRENT_PINGS = 200 
    
    # ============ FLAP PROTECTION ============
    FAIL_THRESHOLD = 3         # 3 fails = DOWN (30 seconds)
    SUCCESS_THRESHOLD = 2      # 2 successes = UP (20 seconds)
    
    # Warning thresholds (need consecutive checks too)
    WARNING_PACKET_LOSS = 75   # >75% loss = Warning (was 50, too sensitive)
    WARNING_THRESHOLD = 3      # Need 3 consecutive high-loss checks for Warning
    
    SCHEDULER_API_ENABLED = True