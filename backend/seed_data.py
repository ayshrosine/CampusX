import os
import sys
import uuid
import secrets
import bcrypt
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "assetflow_campus")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def days_ago(d, hours=0, minutes=0):
    return (datetime.now(timezone.utc) - timedelta(days=d, hours=hours, minutes=minutes)).isoformat()

def days_ahead(d, hours=0, minutes=0):
    return (datetime.now(timezone.utc) + timedelta(days=d, hours=hours, minutes=minutes)).isoformat()

def day_str(d_offset):
    return (datetime.now(timezone.utc).date() + timedelta(days=d_offset)).isoformat()

# Password hashes
PASSWORD_ADMIN = bcrypt.hashpw(b"Admin123!", bcrypt.gensalt()).decode()
PASSWORD_CAMPUS = bcrypt.hashpw(b"Campus123!", bcrypt.gensalt()).decode()

# ==============================================================================
# 1. DEPARTMENTS (15 Campus Departments)
# ==============================================================================
DEPARTMENTS = [
    {"department_id": "dept_cs", "name": "Computer Science", "type": "academic", "head": "Dr. Priya Ramesh", "status": "Active"},
    {"department_id": "dept_mech", "name": "Mechanical", "type": "academic", "head": "Dr. Rajesh Sharma", "status": "Active"},
    {"department_id": "dept_civil", "name": "Civil", "type": "academic", "head": "Dr. Amit Verma", "status": "Active"},
    {"department_id": "dept_ee", "name": "Electrical & Electronics", "type": "academic", "head": "Dr. Sunita Rao", "status": "Active"},
    {"department_id": "dept_ece", "name": "Electronics & Communication", "type": "academic", "head": "Dr. Sandeep Kulkarni", "status": "Active"},
    {"department_id": "dept_biotech", "name": "Biotechnology", "type": "academic", "head": "Dr. Deepak Joshi", "status": "Active"},
    {"department_id": "dept_arch", "name": "Architecture & Planning", "type": "academic", "head": "Prof. Radhika Shenoy", "status": "Active"},
    {"department_id": "dept_physics", "name": "Physics & Materials", "type": "academic", "head": "Dr. Hemant Pandey", "status": "Active"},
    {"department_id": "dept_chem", "name": "Chemistry & Life Sciences", "type": "academic", "head": "Dr. Vandana Saxena", "status": "Active"},
    {"department_id": "dept_admin", "name": "Administration", "type": "administrative", "head": "Rohan Kapoor", "status": "Active"},
    {"department_id": "dept_sports", "name": "Sports", "type": "support", "head": "Coach Vikram Rathore", "status": "Active"},
    {"department_id": "dept_library", "name": "Central Library", "type": "support", "head": "Dr. Meera Nambiar", "status": "Active"},
    {"department_id": "dept_it", "name": "Campus IT Services", "type": "support", "head": "Kavita Deshmukh", "status": "Active"},
    {"department_id": "dept_media", "name": "Media & Communications", "type": "support", "head": "Geeta Paul", "status": "Active"},
    {"department_id": "dept_health", "name": "Medical & Health Centre", "type": "support", "head": "Dr. Alok Sharma", "status": "Active"},
]

# ==============================================================================
# 2. CATEGORIES (10 Categories)
# ==============================================================================
CATEGORIES = [
    {"category_id": "cat_it", "name": "IT Equipment", "example_items": "Laptops, Desktops, Projectors, Tablets, Workstations, Displays", "warranty_tracked": True, "amc_tracked": True},
    {"category_id": "cat_lab", "name": "Lab Equipment", "example_items": "Oscilloscopes, Spectrophotometers, Centrifuges, 3D Printers, Microscopes", "warranty_tracked": True, "amc_tracked": True},
    {"category_id": "cat_machinery", "name": "Workshop Machinery", "example_items": "CNC Milling Units, Lathes, Drill Presses, Welding Units, Hydraulic Presses", "warranty_tracked": True, "amc_tracked": True},
    {"category_id": "cat_media", "name": "Media Equipment", "example_items": "DSLR Cameras, Studio Microphones, Audio Mixers, Video Recorders, Lights", "warranty_tracked": True, "amc_tracked": False},
    {"category_id": "cat_room", "name": "Room", "example_items": "Seminar Halls, Conference Rooms, Auditorium, Smart Classrooms, Boardrooms", "warranty_tracked": False, "amc_tracked": False},
    {"category_id": "cat_vehicle", "name": "Vehicle", "example_items": "College Buses, Campus Shuttles, Utility Vans, Ambulances, Electric Buggies", "warranty_tracked": True, "amc_tracked": True},
    {"category_id": "cat_sports", "name": "Sports Gear", "example_items": "Cricket Kits, Basketballs, Gym Racks, Tennis Equipment, Athletic Kits", "warranty_tracked": False, "amc_tracked": False},
    {"category_id": "cat_furniture", "name": "Office & Furniture", "example_items": "Ergonomic Chairs, Executive Desks, Conference Tables, Steel Filing Cabinets", "warranty_tracked": True, "amc_tracked": False},
    {"category_id": "cat_network", "name": "Network Infrastructure", "example_items": "Core Switches, Wi-Fi 6 APs, Edge Routers, Firewall Appliances, Server Racks", "warranty_tracked": True, "amc_tracked": True},
    {"category_id": "cat_safety", "name": "Medical & Safety", "example_items": "Defibrillators (AED), First Aid Trauma Stations, Eye Wash Units, Gas Monitors", "warranty_tracked": True, "amc_tracked": True},
]

# ==============================================================================
# 3. USERS (28 Campus Users across all roles and departments)
# ==============================================================================
USERS = [
    # Admins
    {"user_id": "user_demo_admin", "name": "Rohan Kapoor", "email": "admin@assetflow.edu", "role": "Admin", "department": "Administration", "status": "Active", "phone": "+91 98201 10001", "password_hash": PASSWORD_ADMIN},
    {"user_id": "user_admin_neha", "name": "Dr. Neha Agarwal", "email": "neha.director@assetflow.edu", "role": "Admin", "department": "Administration", "status": "Active", "phone": "+91 98201 10002", "password_hash": PASSWORD_CAMPUS},
    # Asset Managers
    {"user_id": "user_demo_assetflow", "name": "Maya Iyer", "email": "demo@assetflow.edu", "role": "Asset Manager", "department": "Computer Science", "status": "Active", "phone": "+91 98201 20001", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_mgr_kavita", "name": "Kavita Deshmukh", "email": "kavita.manager@assetflow.edu", "role": "Asset Manager", "department": "Campus IT Services", "status": "Active", "phone": "+91 98201 20002", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_mgr_suresh", "name": "Suresh Nair", "email": "suresh.stores@assetflow.edu", "role": "Asset Manager", "department": "Administration", "status": "Active", "phone": "+91 98201 20003", "password_hash": PASSWORD_CAMPUS},
    # HODs
    {"user_id": "user_demo_priya", "name": "Dr. Priya Ramesh", "email": "priya@assetflow.edu", "role": "HOD", "department": "Computer Science", "status": "Active", "phone": "+91 98201 30001", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_hod_rajesh", "name": "Dr. Rajesh Sharma", "email": "rajesh.hod@assetflow.edu", "role": "HOD", "department": "Mechanical", "status": "Active", "phone": "+91 98201 30002", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_hod_amit", "name": "Dr. Amit Verma", "email": "amit.civil@assetflow.edu", "role": "HOD", "department": "Civil", "status": "Active", "phone": "+91 98201 30003", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_hod_sunita", "name": "Dr. Sunita Rao", "email": "sunita.ee@assetflow.edu", "role": "HOD", "department": "Electrical & Electronics", "status": "Active", "phone": "+91 98201 30004", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_hod_vikram", "name": "Coach Vikram Rathore", "email": "vikram.sports@assetflow.edu", "role": "HOD", "department": "Sports", "status": "Active", "phone": "+91 98201 30005", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_hod_meera", "name": "Dr. Meera Nambiar", "email": "meera.library@assetflow.edu", "role": "HOD", "department": "Central Library", "status": "Active", "phone": "+91 98201 30006", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_hod_deepak", "name": "Dr. Deepak Joshi", "email": "deepak.biotech@assetflow.edu", "role": "HOD", "department": "Biotechnology", "status": "Active", "phone": "+91 98201 30007", "password_hash": PASSWORD_CAMPUS},
    # Employees / Technicians
    {"user_id": "user_demo_arjun", "name": "Arjun Menon", "email": "arjun@assetflow.edu", "role": "Employee", "department": "Mechanical", "status": "Active", "phone": "+91 98201 40001", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_emp_manish", "name": "Manish Kulkarni", "email": "manish.lab@assetflow.edu", "role": "Employee", "department": "Computer Science", "status": "Active", "phone": "+91 98201 40002", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_emp_anita", "name": "Prof. Anita Sen", "email": "anita.faculty@assetflow.edu", "role": "Employee", "department": "Electrical & Electronics", "status": "Active", "phone": "+91 98201 40003", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_emp_rahul", "name": "Rahul Pillai", "email": "rahul.mech@assetflow.edu", "role": "Employee", "department": "Mechanical", "status": "Active", "phone": "+91 98201 40004", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_emp_tarun", "name": "Tarun Bhatia", "email": "tarun.it@assetflow.edu", "role": "Employee", "department": "Campus IT Services", "status": "Active", "phone": "+91 98201 40005", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_emp_geeta", "name": "Geeta Paul", "email": "geeta.media@assetflow.edu", "role": "Employee", "department": "Media & Communications", "status": "Active", "phone": "+91 98201 40006", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_emp_alok", "name": "Dr. Alok Sharma", "email": "dr.sharma.med@assetflow.edu", "role": "Employee", "department": "Medical & Health Centre", "status": "Active", "phone": "+91 98201 40007", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_emp_swapna", "name": "Swapna Mukhopadhyay", "email": "swapna.arch@assetflow.edu", "role": "Employee", "department": "Architecture & Planning", "status": "Active", "phone": "+91 98201 40008", "password_hash": PASSWORD_CAMPUS},
    # Students
    {"user_id": "user_demo_ananya", "name": "Ananya Rao", "email": "ananya@assetflow.edu", "role": "Student", "department": "Computer Science", "status": "Active", "roll_number": "CSE21A004", "phone": "+91 98201 50001", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_demo_vikram", "name": "Vikram Shah", "email": "vikram@assetflow.edu", "role": "Student", "department": "Mechanical", "status": "Pending", "roll_number": "ME22B018", "phone": "+91 98201 50002", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_stu_karan", "name": "Karan Patel", "email": "karan.student@assetflow.edu", "role": "Student", "department": "Computer Science", "status": "Active", "roll_number": "CSE22B033", "phone": "+91 98201 50003", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_stu_sara", "name": "Sara Thomas", "email": "sara.student@assetflow.edu", "role": "Student", "department": "Civil", "status": "Active", "roll_number": "CE21C011", "phone": "+91 98201 50004", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_stu_divya", "name": "Divya Krishnan", "email": "divya.student@assetflow.edu", "role": "Student", "department": "Biotechnology", "status": "Active", "roll_number": "BT23D005", "phone": "+91 98201 50005", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_stu_aditya", "name": "Aditya Mishra", "email": "aditya.student@assetflow.edu", "role": "Student", "department": "Mechanical", "status": "Pending", "roll_number": "ME23B045", "phone": "+91 98201 50006", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_stu_pooja", "name": "Pooja Hegde", "email": "pooja.student@assetflow.edu", "role": "Student", "department": "Electrical & Electronics", "status": "Pending", "roll_number": "EE22A019", "phone": "+91 98201 50007", "password_hash": PASSWORD_CAMPUS},
    {"user_id": "user_stu_rohit", "name": "Rohit Verma", "email": "rohit.student@assetflow.edu", "role": "Student", "department": "Architecture & Planning", "status": "Inactive", "roll_number": "AR21A007", "phone": "+91 98201 50008", "password_hash": PASSWORD_CAMPUS},
]

# ==============================================================================
# Helper to build 260 realistic campus assets
# ==============================================================================
def generate_assets():
    assets = []
    
    # Pre-defined core anchors to ensure 100% backward compatibility
    anchors = [
        ("ast_seed_0", "AF-2025-1000", "Oscilloscope TBS1202", "Lab Equipment", "Turing Block · Electronics Lab 301", "Computer Science", "Allocated", "Dr. Maya Iyer", True, 68000.0, "2024-02-10", "2027-02-10", "Tektronix India", "Apex Lab Services", "SN-TEK-88102"),
        ("ast_seed_1", "AF-2025-1001", "Epson Projector EB-X06", "IT Equipment", "Academic Block · Seminar Hall 2", "Administration", "Available", None, True, 42500.0, "2024-05-18", "2026-05-18", "Epson India Pvt Ltd", "AV Tech Solutions", "SN-EPS-33419"),
        ("ast_seed_2", "AF-2025-1002", "CNC Milling Unit", "Workshop Machinery", "Mechanical Workshop · Bay 1", "Mechanical", "Under Maintenance", None, False, 850000.0, "2023-08-14", "2026-08-14", "Haas Automation", "Precision Machine AMC", "SN-HAA-99214"),
        ("ast_seed_3", "AF-2025-1003", "3D Printer Pro", "Lab Equipment", "Innovation Hub · Lab 102", "Computer Science", "Available", None, True, 125000.0, "2024-11-20", "2027-11-20", "Ultimaker BV", "3D Printing Systems India", "SN-ULT-44821"),
        ("ast_seed_4", "AF-2025-1004", "Canon EOS 90D DSLR", "Media Equipment", "Media Wing · Studio A", "Administration", "Allocated", "Geeta Paul", False, 98000.0, "2023-10-05", "2025-10-05", "Canon Pro Solutions", "Canon AMC Care", "SN-CAN-12903"),
        ("ast_seed_5", "AF-2025-1005", "Sports Kit — Cricket Tournament", "Sports Gear", "Sports Complex · Equipment Room", "Sports", "Available", None, True, 34000.0, "2025-01-15", "2026-01-15", "SG Cricket Sports India", "", "SN-SG-55018"),
        ("ast_demo_laptop1", "AF-0006", "Dell Latitude 5540 Laptop", "IT Equipment", "Turing Block · Floor 3", "Computer Science", "Available", None, True, 89000.0, "2024-07-10", "2027-07-10", "Dell Technologies", "Dell ProSupport Plus", "SN-DEL-99014"),
        ("ast_demo_room1", "AF-2025-2001", "Seminar Hall A", "Room", "Academic Block · Floor 2", "Administration", "Available", None, True, 0.0, "2022-01-01", "", "Campus Infrastructure", "Estates Directorate", "ROOM-ACAD-201"),
        ("ast_demo_room2", "AF-2025-2002", "Conference Room B", "Room", "Admin Block · Floor 1", "Administration", "Available", None, True, 0.0, "2022-01-01", "", "Campus Infrastructure", "Estates Directorate", "ROOM-ADMN-102"),
        ("ast_demo_proj1", "AF-2025-2003", "Epson Projector EB-X06 (AV Store)", "IT Equipment", "Administration · AV Store", "Administration", "Available", None, True, 44000.0, "2024-04-12", "2026-04-12", "Epson India Pvt Ltd", "AV Tech Solutions", "SN-EPS-88312"),
        ("ast_demo_vehicle1", "AF-2025-2004", "College Bus #1 (32-seater)", "Vehicle", "Transport Bay · Bay 1", "Administration", "Available", None, True, 2650000.0, "2023-04-10", "2028-04-10", "Eicher Commercial Vehicles", "Eicher Fleet Care", "REG-MH12-AF-2001"),
    ]
    
    for aid, tag, name, cat, loc, dept, status, holder, bookable, cost, pdate, wdate, supp, amc, sn in anchors:
        assets.append({
            "asset_id": aid,
            "tag": tag,
            "name": name,
            "category": cat,
            "location": loc,
            "department": dept,
            "status": status,
            "holder": holder,
            "expected_return_at": days_ahead(14) if status == "Allocated" else None,
            "serial": sn,
            "bookable": bookable,
            "purchase_cost": cost,
            "purchase_date": pdate,
            "warranty_end": wdate,
            "supplier": supp,
            "amc_provider": amc,
            "notes": "Verified campus anchor asset",
            "updated_at": days_ago(1, hours=2),
            "created_at": days_ago(120),
        })

    # Catalog templates to generate remaining 249 assets (total = 260)
    # We will systematically distribute across 10 categories, 15 departments, and 5 statuses
    catalog = [
        # (Name, Category, Dept, Location, Cost, Supplier, AMC, Bookable)
        # --- IT Equipment (35 items) ---
        ("MacBook Pro 16\" M3 Max", "IT Equipment", "Computer Science", "Turing Block · AI Research Lab 402", 249000.0, "Apple Enterprise India", "AppleCare+ for Enterprise", False),
        ("Dell Precision 3660 Workstation", "IT Equipment", "Computer Science", "Turing Block · Graphics Lab 204", 165000.0, "Dell Technologies", "Dell ProSupport Plus", False),
        ("HP Z4 G5 Workstation Tower", "IT Equipment", "Civil", "Civil CAD Computing Lab", 152000.0, "HP Enterprise", "HP Onsite Gold", False),
        ("Lenovo ThinkPad T14 Gen 4", "IT Equipment", "Electrical & Electronics", "Newton Block · Faculty Room 302", 94000.0, "Lenovo India", "Premier Support Plus", False),
        ("HP EliteBook 840 G10", "IT Equipment", "Administration", "Admin Block · Registrar Suite", 89000.0, "HP Enterprise", "HP Onsite Gold", False),
        ("iPad Air 11\" M2 128GB", "IT Equipment", "Architecture & Planning", "Design Studio · Digital Bay", 62000.0, "Apple Enterprise India", "AppleCare+", True),
        ("Wacom Cintiq 16 Pro Tablet", "IT Equipment", "Architecture & Planning", "Design Studio · Animation Lab", 78000.0, "Wacom India", "Wacom Care", False),
        ("BenQ MH733 Full HD Projector", "IT Equipment", "Mechanical", "Newton Block · Lecture Hall 101", 58000.0, "BenQ India", "BenQ Corporate Warranty", True),
        ("Sony VPL-PHZ50 Laser Projector", "IT Equipment", "Computer Science", "Turing Auditorium Annex", 185000.0, "Sony Professional India", "Sony PrimeSupport", True),
        ("Samsung Flip Pro 75\" Interactive Display", "IT Equipment", "Administration", "Academic Council Boardroom", 260000.0, "Samsung Electronics", "Samsung Enterprise Care", True),
        ("ViewSonic IFP6550 Smart Board", "IT Equipment", "Biotechnology", "BioTech Wing · Lecture Room 2", 145000.0, "ViewSonic India", "ViewSonic Advance AMC", True),
        ("HP LaserJet Enterprise M608dn", "IT Equipment", "Central Library", "Library · Reference Desk Floor 1", 62000.0, "HP Enterprise", "HP Print Care", False),
        ("Canon imageRUNNER ADVANCE DX 2630", "IT Equipment", "Administration", "Admin Central Dispatch & Records", 210000.0, "Canon Pro Solutions", "Canon Comprehensive AMC", False),
        ("Elmo MX-P3 4K Document Camera", "IT Equipment", "Chemistry & Life Sciences", "Chemical Sciences Amphitheatre", 48000.0, "Elmo Visual Systems", "", False),
        ("AVerVision M11-8MV Mechanical Visualizer", "IT Equipment", "Physics & Materials", "Physics Demonstration Hall", 39000.0, "AVer Information", "", False),
        ("Dell UltraSharp 32\" 4K U3223QE", "IT Equipment", "Computer Science", "HPC Server Control Room", 78000.0, "Dell Technologies", "Dell ProSupport", False),
        ("Asus ProArt PA278CV Color Display", "IT Equipment", "Media & Communications", "Media Wing · Post-Production Suite", 42000.0, "Asus India", "", False),
        ("Lenovo IdeaPad Gaming Rig", "IT Equipment", "Campus IT Services", "Campus eSports & VR Club", 82000.0, "Lenovo India", "Lenovo Legion Care", True),
        ("Acer Predator Orion 3000 Rig", "IT Equipment", "Computer Science", "Virtual Reality Lab", 128000.0, "Acer India", "Acer Premier AMC", True),
        ("Fujitsu ScanSnap iX1600 Scanner", "IT Equipment", "Central Library", "Library Archival Digitization Unit", 54000.0, "Fujitsu Systems", "", False),
        ("Epson EcoTank Pro L15160 A3 Printer", "IT Equipment", "Civil", "Civil Drawing & Blueprint Office", 85000.0, "Epson India Pvt Ltd", "Epson Onsite", False),
        ("Zebra ZT411 Industrial RFID Printer", "IT Equipment", "Campus IT Services", "Asset Tagging Center", 115000.0, "Zebra Technologies", "Zebra OneCare", False),
        ("Microsoft Surface Laptop Studio 2", "IT Equipment", "Administration", "Vice-Chancellor Secretariat", 215000.0, "Microsoft India", "Surface Complete for Business", False),
        ("Dell Latitude 7440 Ultrabook", "IT Equipment", "Campus IT Services", "Network Operations Centre", 102000.0, "Dell Technologies", "Dell ProSupport Plus", True),
        ("Lenovo ThinkCentre M70q Tiny PC", "IT Equipment", "Central Library", "Library Public OPAC Terminal 1", 45000.0, "Lenovo India", "", False),
        ("Lenovo ThinkCentre M70q Tiny PC #2", "IT Equipment", "Central Library", "Library Public OPAC Terminal 2", 45000.0, "Lenovo India", "", False),
        ("Lenovo ThinkCentre M70q Tiny PC #3", "IT Equipment", "Central Library", "Library Public OPAC Terminal 3", 45000.0, "Lenovo India", "", False),
        ("HP Pro Tower 280 G9 Desktop", "IT Equipment", "Administration", "Accounts Payable Cell", 49000.0, "HP Enterprise", "", False),
        ("HP Pro Tower 280 G9 Desktop #2", "IT Equipment", "Administration", "Student Admissions Office", 49000.0, "HP Enterprise", "", False),
        ("Dell OptiPlex 7010 Micro Desktop", "IT Equipment", "Medical & Health Centre", "Health Centre Pharmacy Desk", 52000.0, "Dell Technologies", "", False),
        ("Promethean ActivPanel 75\" 4K", "IT Equipment", "Electronics & Communication", "VLSI Seminar Room 108", 225000.0, "Promethean Global", "Promethean Support", True),
        ("Optoma ZH406 Laser Projector", "IT Equipment", "Physics & Materials", "Physics Lecture Theatre 1", 135000.0, "Optoma India", "Optoma Care", True),
        ("Dell Latitude 3440 Laptop #4", "IT Equipment", "Sports", "Athletics Coach Bureau", 68000.0, "Dell Technologies", "Dell ProSupport", True),
        ("Dell Latitude 3440 Laptop #5", "IT Equipment", "Mechanical", "SAE Club Garage Annex", 68000.0, "Dell Technologies", "Dell ProSupport", True),

        # --- Lab Equipment (40 items) ---
        ("Keysight InfiniiVision DSOX1204G Oscilloscope", "Lab Equipment", "Electronics & Communication", "VLSI & Embedded Lab", 112000.0, "Keysight Technologies", "Keysight Assurance", True),
        ("Rigol DS1054Z 4-Channel Oscilloscope", "Lab Equipment", "Electrical & Electronics", "Circuits Lab · Bench 1", 38000.0, "Rigol Technologies", "", True),
        ("Siglent SDG1032X Function Generator", "Lab Equipment", "Electrical & Electronics", "Circuits Lab · Bench 2", 42000.0, "Siglent Scientific", "", False),
        ("Rigol DG1022Z Waveform Generator", "Lab Equipment", "Electronics & Communication", "Analog Lab · Station 4", 36000.0, "Rigol Technologies", "", False),
        ("Fluke 8846A 6.5 Digit Precision Multimeter", "Lab Equipment", "Physics & Materials", "Materials Characterization Lab", 125000.0, "Fluke South Asia", "Fluke Calibration Gold", False),
        ("Keysight E3631A Triple Output DC Power Supply", "Lab Equipment", "Electronics & Communication", "RF Microwave Lab", 82000.0, "Keysight Technologies", "", False),
        ("Korad KA3005P Programmable Power Supply", "Lab Equipment", "Computer Science", "IoT Hardware Prototyping Lab", 18500.0, "Korad Electronics", "", False),
        ("Creality Ender 3 S1 Pro 3D Printer", "Lab Equipment", "Mechanical", "CAD/CAM Prototyping Studio", 46000.0, "Creality 3D India", "", True),
        ("Prusa Research Original MK4 3D Printer", "Lab Equipment", "Electronics & Communication", "Hardware Innovation Cell", 88000.0, "Prusa Research", "Prusa Partner Support", True),
        ("Formlabs Form 3+ SLA Resin 3D Printer", "Lab Equipment", "Biotechnology", "Tissue Engineering Lab", 390000.0, "Formlabs Inc", "Formlabs Pro Plan", False),
        ("Thermo Fisher NanoDrop One Spectrophotometer", "Lab Equipment", "Biotechnology", "Genomics & Molecular Lab", 820000.0, "Thermo Fisher Scientific", "Thermo Fisher Total Care", False),
        ("Shimadzu UV-1900i UV-Vis Spectrophotometer", "Lab Equipment", "Chemistry & Life Sciences", "Spectroscopy Unit Room 204", 650000.0, "Shimadzu India", "Shimadzu Precision AMC", False),
        ("Agilent 1260 Infinity II HPLC System", "Lab Equipment", "Chemistry & Life Sciences", "Analytical Chromatography Lab", 1450000.0, "Agilent Technologies", "Agilent CrossLab Advantage", False),
        ("Eppendorf 5424R Refrigerated Microcentrifuge", "Lab Equipment", "Biotechnology", "Cell Culture Facility", 340000.0, "Eppendorf India", "Eppendorf Service Plus", False),
        ("Remi R-8C Laboratory Centrifuge", "Lab Equipment", "Medical & Health Centre", "Clinical Pathology Testing Lab", 24000.0, "Remi Electrotechnik", "", False),
        ("Memmert IN110 Natural Convection Incubator", "Lab Equipment", "Biotechnology", "Microbiology Isolation Suite", 185000.0, "Memmert GmbH", "Memmert Extended Care", False),
        ("Mettler Toledo ME204 Analytical Balance 0.1mg", "Lab Equipment", "Chemistry & Life Sciences", "Balance Room Level 1", 92000.0, "Mettler Toledo", "Mettler Calibration Guard", False),
        ("Sartorius Practum 224-1S Analytical Balance", "Lab Equipment", "Physics & Materials", "Thin Films Lab", 86000.0, "Sartorius India", "Sartorius Service", False),
        ("Bio-Rad T100 Thermal Cycler (PCR)", "Lab Equipment", "Biotechnology", "Molecular Diagnostics Suite", 280000.0, "Bio-Rad Laboratories", "Bio-Rad Expert Care", False),
        ("Applied Biosystems SimpliAmp Thermal Cycler", "Lab Equipment", "Biotechnology", "Gene Expression Lab", 310000.0, "Thermo Fisher Scientific", "Thermo Fisher Onsite", False),
        ("Olympus CX23 Binocular Microscope #1", "Lab Equipment", "Chemistry & Life Sciences", "Biology Lab · Station 1", 38000.0, "Olympus Life Science", "", True),
        ("Olympus CX23 Binocular Microscope #2", "Lab Equipment", "Chemistry & Life Sciences", "Biology Lab · Station 2", 38000.0, "Olympus Life Science", "", True),
        ("Nikon Eclipse E100 Biological Microscope", "Lab Equipment", "Biotechnology", "Histology Preparation Room", 52000.0, "Nikon Healthcare India", "", False),
        ("Leica DM500 Educational Microscope", "Lab Equipment", "Medical & Health Centre", "Diagnostic Triage Unit", 48000.0, "Leica Microsystems", "", False),
        ("Instron 3369 Universal Testing Machine 50kN", "Lab Equipment", "Civil", "Concrete & Structural Mechanics Bay", 1250000.0, "Instron India", "Instron Premier Cal", False),
        ("Heico Automatic Compression Testing Machine 2000kN", "Lab Equipment", "Civil", "Concrete Strength Testing Pit", 540000.0, "Heico Dynamics", "Heico Field AMC", False),
        ("Tinius Olsen Charpy Impact Tester IT406", "Lab Equipment", "Mechanical", "Metallurgy Lab Bay 3", 380000.0, "Tinius Olsen", "Tinius Annual Cal", False),
        ("Mitutoyo Rockwell Hardness Tester HR-210MR", "Lab Equipment", "Mechanical", "Quality Inspection Lab", 195000.0, "Mitutoyo South Asia", "Mitutoyo Calibration AMC", False),
        ("Mahr Federal Pocket Surf Portable Profilometer", "Lab Equipment", "Mechanical", "Metrology & Surface Lab", 145000.0, "Mahr Metrology", "", False),
        ("Rohde & Schwarz Spectrum Analyzer FPC1500", "Lab Equipment", "Electronics & Communication", "RF Communications Wing", 295000.0, "Rohde & Schwarz India", "R&S Care", False),
        ("Keithley 2450 Interactive SourceMeter SMU", "Lab Equipment", "Physics & Materials", "Semiconductor Device Lab", 385000.0, "Tektronix India", "Tektronix Gold Support", False),
        ("Olympus DSX1000 Opto-Digital Microscope", "Lab Equipment", "Physics & Materials", "Advanced Microscopy Center", 1180000.0, "Olympus Scientific", "Olympus Comprehensive", False),
        ("Spectra-Physics He-Ne Laser Source 632.8nm", "Lab Equipment", "Physics & Materials", "Optics Darkroom Bay 4", 85000.0, "MKS Newport", "", False),
        ("Anton Paar ViscoQC 300 Rotational Viscometer", "Lab Equipment", "Chemistry & Life Sciences", "Polymer Characterization Bay", 290000.0, "Anton Paar India", "Anton Paar Care", False),
        ("Labconco Purifier Logic+ Class II Biosafety Cabinet", "Lab Equipment", "Biotechnology", "BSL-2 Clean Isolation Wing", 580000.0, "Labconco Corp", "Labconco Certification Plus", False),
        ("Thermo Scientific Barnstead GenPure Water System", "Lab Equipment", "Biotechnology", "Ultra-Pure Central Water Room", 340000.0, "Thermo Fisher Scientific", "Water System Annual Filter AMC", False),
        ("Cole-Parmer Ultrasonic Homogenizer Sonicator", "Lab Equipment", "Biotechnology", "Nanomaterials Prep Lab", 165000.0, "Cole-Parmer India", "", False),
        ("Yamato DP43 Vacuum Drying Oven 91L", "Lab Equipment", "Chemistry & Life Sciences", "Inorganic Synthesis Room", 190000.0, "Yamato Scientific", "", False),
        ("Julabo F25-ED Refrigerated Heating Circulator", "Lab Equipment", "Chemistry & Life Sciences", "Thermal Analysis Station", 240000.0, "Julabo India", "Julabo Cool AMC", False),
        ("Zeiss Stemi 508 Stereo Microscope", "Lab Equipment", "Civil", "Geotechnical & Soil Mechanics Unit", 125000.0, "Carl Zeiss India", "", False),

        # --- Workshop Machinery (25 items) ---
        ("Tormach PCNC 440 Personal CNC Mill", "Workshop Machinery", "Mechanical", "Mechanical Workshop · CNC Cell", 480000.0, "Tormach Inc", "CNC Support Network", False),
        ("Colchester Student 2500 Geared Head Lathe", "Workshop Machinery", "Mechanical", "Machine Shop · Floor Bay 1", 390000.0, "Colchester Lathes", "Lathe Maintenance Corp", False),
        ("HMT Heavy Duty Precision Lathe NH-26", "Workshop Machinery", "Mechanical", "Machine Shop · Floor Bay 2", 52000.0, "HMT Machine Tools", "HMT National AMC", False),
        ("Bridgeport Series I Standard Vertical Mill", "Workshop Machinery", "Mechanical", "Machine Shop · Floor Bay 3", 640000.0, "Hardinge Inc", "Bridgeport Field Support", False),
        ("Jet J-2530 15\" Floor Model Drill Press", "Workshop Machinery", "Mechanical", "Mechanical Workshop · Drilling Bay", 85000.0, "Jet Tools India", "", False),
        ("Miller Multimatic 220 AC/DC MIG/TIG Welder", "Workshop Machinery", "Mechanical", "Welding & Fabrication Enclosure", 195000.0, "Miller Electric", "Miller WeldCare", False),
        ("Lincoln Electric Power Wave C300 Welder", "Workshop Machinery", "Mechanical", "Robotic Welding Cell", 360000.0, "Lincoln Electric India", "Lincoln Gold Care", False),
        ("Amada 50-Ton Hydraulic CNC Press Brake", "Workshop Machinery", "Mechanical", "Sheet Metal Forming Shop", 920000.0, "Amada India Pvt Ltd", "Amada Certified AMC", False),
        ("DoALL C-916M Horizontal Metal Cutting Bandsaw", "Workshop Machinery", "Mechanical", "Raw Material Sizing Bay", 175000.0, "DoALL Sawing", "", False),
        ("DeWalt DW872 Multi-Cutter 14\" Chop Saw", "Workshop Machinery", "Civil", "Civil Carpentry & Structural Yard", 38000.0, "DeWalt India", "", False),
        ("Makita 2012NB 12\" Portable Surface Planer", "Workshop Machinery", "Architecture & Planning", "Model Making & Woodcraft Yard", 52000.0, "Makita Power Tools", "", True),
        ("SawStop 10\" Professional Cabinet Table Saw", "Workshop Machinery", "Architecture & Planning", "Architectural Woodshop", 195000.0, "SawStop USA", "SawStop Safety Service", False),
        ("Bosch GCO 14-24 J Metal Cut-Off Grinder", "Workshop Machinery", "Civil", "Civil Construction Testing Shed", 18500.0, "Bosch Power Tools", "", False),
        ("Pfeiffer Balzers Duo 016B Vacuum Rotary Pump", "Workshop Machinery", "Physics & Materials", "High Vacuum Tech Annex", 240000.0, "Pfeiffer Vacuum India", "", False),
        ("Atlas Copco GA 11 VSD+ Rotary Screw Compressor", "Workshop Machinery", "Campus IT Services", "Central Pneumatics & Utility Utility", 380000.0, "Atlas Copco India", "Atlas Copco TotalCare", False),
        ("Ingersoll Rand UP6-15 Air Compressor 15HP", "Workshop Machinery", "Mechanical", "Workshop Pneumatics Utility Room", 280000.0, "Ingersoll Rand India", "IR Air Care", False),
        ("Karcher HD 7/14-4 M Professional Pressure Washer", "Workshop Machinery", "Administration", "Estate Maintenance Wash Bay", 78000.0, "Karcher Cleaning Systems", "", True),
        ("Hitachi H65SD3 Heavy Duty Demolition Breaker", "Workshop Machinery", "Civil", "Concrete Demolition & Testing Site", 62000.0, "Hikoki Power Tools", "", False),
        ("Stilmax Heavy Duty 100-Ton Hydraulic Shop Press", "Workshop Machinery", "Mechanical", "Forging & Stamping Shed", 185000.0, "Stilmax Industries", "", False),
        ("Surface Grinding Machine SGA 3063AHD", "Workshop Machinery", "Mechanical", "Tool & Die Grinding Bay", 420000.0, "Chevalier Machinery", "Chevalier Service Plus", False),
        ("Cincinnati Milacron Universal Tool & Cutter Grinder", "Workshop Machinery", "Mechanical", "Toolroom Annex Room 12", 340000.0, "Cincinnati Machine", "", False),
        ("Omax ProtoMAX Abrasive Waterjet Cutter", "Workshop Machinery", "Mechanical", "Advanced Machining Center", 1450000.0, "Omax Corporation", "Omax Precision AMC", False),
        ("Epilog Fusion Pro 48 Laser Engraver / Cutter 80W", "Workshop Machinery", "Architecture & Planning", "Digital Fabrication Studio", 780000.0, "Epilog Laser India", "Epilog TechCare", True),
        ("Roland MDX-50 Benchtop CNC Mill", "Workshop Machinery", "Computer Science", "Rapid Prototyping FabLab", 520000.0, "Roland DGA", "Roland Care", True),
        ("Lincoln Electric Tomahawk 1000 Plasma Cutter", "Workshop Machinery", "Mechanical", "Sheet Metal Cutting Bay", 165000.0, "Lincoln Electric", "", False),

        # --- Media Equipment (25 items) ---
        ("Sony Alpha A7 IV Mirrorless Camera Body", "Media Equipment", "Media & Communications", "Media Wing · Equipment Locker", 189000.0, "Sony Professional India", "Sony Pro Protection", True),
        ("Sony FE 24-70mm f/2.8 GM II Lens", "Media Equipment", "Media & Communications", "Media Wing · Lens Safe", 175000.0, "Sony Professional India", "", True),
        ("Sony FE 70-200mm f/2.8 GM OSS II Lens", "Media Equipment", "Media & Communications", "Media Wing · Lens Safe", 210000.0, "Sony Professional India", "", True),
        ("Canon XA50 4K UHD Pro Camcorder", "Media Equipment", "Media & Communications", "Campus News Recording Desk", 142000.0, "Canon Pro Solutions", "Canon ProCare", True),
        ("Panasonic Lumix GH6 Cinema Camera Kit", "Media Equipment", "Media & Communications", "Media Production Lab", 168000.0, "Panasonic India", "Panasonic Lumix Pro", True),
        ("Sony FX3 Cinema Line Full-Frame Camera", "Media Equipment", "Media & Communications", "Advanced Film Studio Bay 1", 320000.0, "Sony Professional India", "Sony ProSupport", True),
        ("Blackmagic Pocket Cinema Camera 6K Pro", "Media Equipment", "Media & Communications", "Advanced Film Studio Bay 2", 215000.0, "Blackmagic Design", "", True),
        ("Shure SM7B Vocal Dynamic Microphone #1", "Media Equipment", "Media & Communications", "Podcast Studio · Mic Pod 1", 38000.0, "Shure South Asia", "", True),
        ("Shure SM7B Vocal Dynamic Microphone #2", "Media Equipment", "Media & Communications", "Podcast Studio · Mic Pod 2", 38000.0, "Shure South Asia", "", True),
        ("Rode Wireless PRO Dual Wireless Mic System", "Media Equipment", "Administration", "PR & Institutional Events Store", 36000.0, "Rode Microphones", "", True),
        ("Rode Wireless GO II Dual Mic System", "Media Equipment", "Central Library", "Library MOOC Studio", 26000.0, "Rode Microphones", "", True),
        ("Sennheiser EW-DP ME2 Wireless Lavalier Kit", "Media Equipment", "Media & Communications", "Outdoor Broadcast Kit", 54000.0, "Sennheiser India", "", True),
        ("Focusrite Scarlett 18i20 USB Audio Interface", "Media Equipment", "Media & Communications", "Audio Engineering Control Room", 48000.0, "Focusrite Novation", "", False),
        ("Rodecaster Pro II Audio Production Console", "Media Equipment", "Media & Communications", "Podcast Studio Main Desk", 68000.0, "Rode Microphones", "", True),
        ("Aputure Amaran 200d LED Studio Light #1", "Media Equipment", "Media & Communications", "Media Studio Grid Light 1", 28000.0, "Aputure Imaging", "", False),
        ("Aputure Amaran 200d LED Studio Light #2", "Media Equipment", "Media & Communications", "Media Studio Grid Light 2", 28000.0, "Aputure Imaging", "", False),
        ("Godox SL-60W Continuous Studio Light Kit", "Media Equipment", "Administration", "Conference Coverage AV Kit", 32000.0, "Godox Photo", "", True),
        ("Manfrotto 504HD Pro Fluid Video Head Tripod", "Media Equipment", "Media & Communications", "Studio Tripod Bay", 48000.0, "Manfrotto Videndum", "", True),
        ("DJI RS 3 Pro Gimbal Stabilizer Combo", "Media Equipment", "Media & Communications", "Mobile Film Unit Trunk", 74000.0, "DJI Enterprise India", "DJI Care Refresh", True),
        ("Yamaha StagePas 600BT Portable PA Sound System", "Media Equipment", "Sports", "Sports Arena PA Control Hub", 94000.0, "Yamaha Music India", "Yamaha Pro Audio AMC", True),
        ("JBL EON One Compact All-in-One Portable PA", "Media Equipment", "Administration", "Open Amphitheatre Audio Locker", 54000.0, "Harman International", "", True),
        ("Blackmagic ATEM Mini Extreme ISO Switcher", "Media Equipment", "Campus IT Services", "Webinar & Convocation Control Rig", 89000.0, "Blackmagic Design", "", True),
        ("Zoom H8 8-Track Handy Portable Audio Recorder", "Media Equipment", "Civil", "Acoustics & Structural Vibration Rig", 36000.0, "Zoom Corporation", "", True),
        ("Atomos Ninja V+ 5.2\" 8K HDMI Raw Monitor", "Media Equipment", "Media & Communications", "Field Cam Rig Monitor Rack", 72000.0, "Atomos Global", "", False),
        ("DJI Mavic 3 Pro Cine Drone with RC Pro", "Media Equipment", "Media & Communications", "Campus Survey & Aerial Filming Box", 285000.0, "DJI Enterprise India", "DJI Care Shield", True),

        # --- Room (20 items - all bookable) ---
        ("Seminar Hall B (Science Wing)", "Room", "Physics & Materials", "Science Block · Floor 1 Room 105", 0.0, "Campus Estates", "Estate Care", True),
        ("Auditorium Main Concert Theatre", "Room", "Administration", "Central Cultural Complex Ground", 0.0, "Campus Estates", "Acoustics AMC", True),
        ("Executive Boardroom (Senate Suite)", "Room", "Administration", "Admin Block · Floor 3 Suite 301", 0.0, "Campus Estates", "Estate Care", True),
        ("Smart Classroom 101 (Interactive)", "Room", "Computer Science", "Turing Block · Floor 1 Room 101", 0.0, "Campus Estates", "Smart Class Care", True),
        ("Smart Classroom 204 (Interactive)", "Room", "Mechanical", "Newton Block · Floor 2 Room 204", 0.0, "Campus Estates", "Smart Class Care", True),
        ("Computer Science Lab 301 (60-Seat)", "Room", "Computer Science", "Turing Block · Floor 3 Lab 301", 0.0, "Campus Estates", "Campus Lab Services", True),
        ("Robotics & AI Arena", "Room", "Computer Science", "Innovation Hub · Floor 1 Arena", 0.0, "Campus Estates", "Robotics Facility", True),
        ("Media & Podcasting Studio Suite", "Room", "Media & Communications", "Media Wing · Level 1 Studio", 0.0, "Campus Estates", "Acoustic Shielding", True),
        ("Civil Structures & Shake Table Bay", "Room", "Civil", "Civil Heavy Engineering Ground Bay", 0.0, "Campus Estates", "Estates Yard", True),
        ("Biotechnology Cleanroom Suite Class 1000", "Room", "Biotechnology", "Life Sciences Tower · Level 2", 0.0, "Campus Estates", "HVAC Clean Air AMC", True),
        ("Architecture Drafting Studio 4", "Room", "Architecture & Planning", "Design Tower · Floor 4 Studio", 0.0, "Campus Estates", "Design Estates", True),
        ("Central Library Quiet Reading Hall", "Room", "Central Library", "Library Tower · Floor 3 Reading Hall", 0.0, "Campus Estates", "Library Facilities", True),
        ("Makerspace & Prototyping Bay", "Room", "Mechanical", "Mechanical Annex · Fabrication Ground", 0.0, "Campus Estates", "Mechanical Workshop Admin", True),
        ("Open Air Amphitheatre (500-Capacity)", "Room", "Administration", "Campus Central Lawns Amphitheatre", 0.0, "Campus Estates", "Estates Grounds", True),
        ("Sports Complex Multipurpose Indoor Court", "Room", "Sports", "Sports Complex · Indoor Arena Hall", 0.0, "Campus Estates", "Sports Facilities Care", True),
        ("Campus Gymnasium & Fitness Centre", "Room", "Sports", "Sports Complex · Level 1 Gym Wing", 0.0, "Campus Estates", "Fitness Equipment Care", True),
        ("Electrical Machines Test Bay", "Room", "Electrical & Electronics", "Power Systems Wing Ground Floor", 0.0, "Campus Estates", "High Voltage Safety", True),
        ("Chemistry Instrumental Analysis Lab", "Room", "Chemistry & Life Sciences", "Chemical Sciences Level 2 Room 208", 0.0, "Campus Estates", "Fume Extraction Care", True),
        ("Placement & Interview Suite A", "Room", "Administration", "Placement Cell · Interview Cubicle 1", 0.0, "Campus Estates", "Corporate Relations", True),
        ("Placement & Interview Suite B", "Room", "Administration", "Placement Cell · Interview Cubicle 2", 0.0, "Campus Estates", "Corporate Relations", True),

        # --- Vehicle (15 items - all bookable) ---
        ("College Bus #2 (45-seater Tata Starbus)", "Vehicle", "Administration", "Transport Bay · Bay 2", 2850000.0, "Tata Motors Commercial", "Tata Fleet Care Plus", True),
        ("College Bus #3 (52-seater Ashok Leyland)", "Vehicle", "Administration", "Transport Bay · Bay 3", 3100000.0, "Ashok Leyland", "Ashok Leyland Alert AMC", True),
        ("College Bus #4 (32-seater Eicher Skyline)", "Vehicle", "Administration", "Transport Bay · Bay 4", 2650000.0, "Eicher Commercial Vehicles", "Eicher Fleet Care", True),
        ("Campus Electric Shuttle Van #1 (14-seater)", "Vehicle", "Administration", "Campus EV Charging Station Bay A", 1650000.0, "Force Motors Urbania", "Force Green Fleet", True),
        ("Campus Electric Shuttle Van #2 (14-seater)", "Vehicle", "Administration", "Campus EV Charging Station Bay B", 1650000.0, "Force Motors Urbania", "Force Green Fleet", True),
        ("Campus Inspection Car (Tata Nexon EV)", "Vehicle", "Administration", "Admin Portico Parking Lot 1", 1540000.0, "Tata Motors Passenger EV", "Tata Motors Gold Plan", True),
        ("Campus Faculty Mobility Car (Maruti Ertiga)", "Vehicle", "Administration", "Admin Portico Parking Lot 2", 1120000.0, "Maruti Suzuki Commercial", "Maruti Onsite Fleet", True),
        ("Campus Utility Pickup (Mahindra Bolero Maxi)", "Vehicle", "Administration", "Estate Maintenance Yard Bay 1", 890000.0, "Mahindra & Mahindra", "Mahindra Commercial AMC", True),
        ("Campus Medical Ambulance (Force Traveller ICU)", "Vehicle", "Medical & Health Centre", "Health Centre Emergency Porch", 2150000.0, "Force Motors Ltd", "Paramedical Vehicle Care", True),
        ("Campus Security Patrol Jeep (Mahindra Thar)", "Vehicle", "Administration", "Main Campus Security Gate 1", 1380000.0, "Mahindra & Mahindra", "Security Fleet Support", True),
        ("Transport Maintenance Buggy (Club Car Carryall)", "Vehicle", "Administration", "Mechanical Workshop Tool Bay", 420000.0, "Club Car Commercial", "", True),
        ("Campus Grounds Tractor (Mahindra 575 DI)", "Vehicle", "Administration", "Horticulture & Grounds Depot", 740000.0, "Mahindra Tractors", "Kisan & Campus Care", True),
        ("Sports Team Mini-Bus (18-seater Swaraj Mazda)", "Vehicle", "Sports", "Sports Complex Parking Strip", 1820000.0, "SML Isuzu Ltd", "SML Fleet Care", True),
        ("Library Mobile Book Bus (Tata Winger)", "Vehicle", "Central Library", "Library Rear Loading Bay", 1280000.0, "Tata Motors Commercial", "Tata Winger Onsite", True),
        ("Campus Forklift Truck 3-Ton (Godrej Diesel)", "Vehicle", "Mechanical", "Central Stores Heavy Warehouse", 980000.0, "Godrej Material Handling", "Godrej LiftCare", True),

        # --- Sports Gear (25 items) ---
        ("Cricket Match Kit Pro — SG English Willow", "Sports Gear", "Sports", "Sports Pavillion · Kit Locker 1", 38000.0, "SG Sports India", "", True),
        ("Cricket Match Kit Practice — SS Kashmir Willow", "Sports Gear", "Sports", "Sports Pavillion · Kit Locker 2", 22000.0, "Sareen Sports", "", True),
        ("Yonex Astrox 88D Pro Badminton Rackets (Set of 4)", "Sports Gear", "Sports", "Badminton Arena Storage", 42000.0, "Yonex Sports", "", True),
        ("Yonex Court Badminton Tournament Net & Posts", "Sports Gear", "Sports", "Badminton Arena Storage", 16000.0, "Yonex Sports", "", False),
        ("Spalding TF-1000 Legacy Basketballs (Set of 10)", "Sports Gear", "Sports", "Basketball Court Store", 28000.0, "Spalding Athletics", "", True),
        ("Spalding Heavy Duty Breakaway Rims (Pair)", "Sports Gear", "Sports", "Basketball Court Main Backboard", 34000.0, "Spalding Athletics", "", False),
        ("FIFA Pro Certified Football Match Balls (Set of 12)", "Sports Gear", "Sports", "Football Equipment Shed", 29000.0, "Nivia Sports", "", True),
        ("Stiga Expert VM 30mm Table Tennis Table #1", "Sports Gear", "Sports", "Indoor Recreation Hall Room 1", 78000.0, "Stiga Sports", "Stiga TT Maintenance", True),
        ("Stiga Expert VM 30mm Table Tennis Table #2", "Sports Gear", "Sports", "Indoor Recreation Hall Room 2", 78000.0, "Stiga Sports", "Stiga TT Maintenance", True),
        ("Body-Solid Pro ClubLine Multi-Station Gym Rig", "Sports Gear", "Sports", "Campus Gymnasium Main Hall", 390000.0, "Body-Solid India", "Gym Maintenance AMC", False),
        ("Olympic Barbell & Bumper Plate Weight Set 250kg", "Sports Gear", "Sports", "Gymnasium Free Weights Bay", 86000.0, "Bullrock Fitness", "", False),
        ("Commercial Motorized Treadmill (Precor TRM 885)", "Sports Gear", "Sports", "Gymnasium Cardio Floor", 320000.0, "Precor Fitness India", "Precor Commercial AMC", False),
        ("Commercial Elliptical Cross Trainer (Life Fitness)", "Sports Gear", "Sports", "Gymnasium Cardio Floor", 260000.0, "Life Fitness India", "Life Fitness AMC", False),
        ("Volleyball Tournament Court System & Antennas", "Sports Gear", "Sports", "Volleyball Sand Court", 19500.0, "Cosco India", "", True),
        ("Cosco Super Volley Match Balls (Set of 8)", "Sports Gear", "Sports", "Volleyball Sand Court Locker", 12000.0, "Cosco India", "", True),
        ("Wilson Pro Staff 97 Tennis Racquets (Set of 4)", "Sports Gear", "Sports", "Tennis Complex Equipment Chest", 48000.0, "Wilson Sporting Goods", "", True),
        ("Lobster Sports Elite Grand 4 Tennis Ball Machine", "Sports Gear", "Sports", "Tennis Court 1 Shed", 195000.0, "Lobster Sports", "Lobster Support", True),
        ("Nelco Track & Field Starting Blocks (Set of 8)", "Sports Gear", "Sports", "Athletic Track Shed", 38000.0, "Nelco India", "", False),
        ("Nelco Championship Javelins 800g (Set of 6)", "Sports Gear", "Sports", "Field Equipment Shed", 29000.0, "Nelco India", "", False),
        ("High Jump Landing Pit Foam Mat 6m x 4m x 0.7m", "Sports Gear", "Sports", "Athletics Field Pit", 185000.0, "Vinex Sports", "", False),
        ("Nivia Premier Handball Balls (Set of 10)", "Sports Gear", "Sports", "Indoor Court Bin 3", 14000.0, "Nivia Sports", "", True),
        ("Carrom Tournament Boards 36\" Champion (Set of 4)", "Sports Gear", "Sports", "Recreation Room Carrom Zone", 18000.0, "Synco Carrom", "", True),
        ("DGT 2010 Digital Chess Clocks & Wooden Boards (Set of 8)", "Sports Gear", "Sports", "Chess Club Room", 24000.0, "DGT Chess International", "", True),
        ("Archery Recurve Bow Match Set (Hoyt Formula)", "Sports Gear", "Sports", "Archery Target Range", 95000.0, "Hoyt Archery", "", True),
        ("Swimming Pool Anti-Turbulence Lane Dividers 25m", "Sports Gear", "Sports", "Aquatics Center Pool Bay", 68000.0, "Competitor Swim", "", False),

        # --- Office & Furniture (25 items) ---
        ("Steelcase Series 1 Ergonomic Mesh Chairs (Lot of 10)", "Office & Furniture", "Administration", "Admin Executive Conference Floor", 195000.0, "Steelcase India", "Steelcase Warranty 12y", False),
        ("Herman Miller Sayl Task Chair", "Office & Furniture", "Computer Science", "HOD Office · Computer Science", 48000.0, "Herman Miller India", "Herman Miller 12-Year", False),
        ("Godrej Interio Quad-Pod Modular Faculty Desk", "Office & Furniture", "Civil", "Civil Staff Room Room 201", 64000.0, "Godrej Interio", "Godrej Institutional Care", False),
        ("Godrej Interio Quad-Pod Modular Faculty Desk #2", "Office & Furniture", "Mechanical", "Mechanical Staff Room 104", 64000.0, "Godrej Interio", "Godrej Institutional Care", False),
        ("Godrej Interio Quad-Pod Modular Faculty Desk #3", "Office & Furniture", "Electrical & Electronics", "EE Faculty Room 302", 64000.0, "Godrej Interio", "Godrej Institutional Care", False),
        ("Executive 16-Seater Solid Oak Conference Table", "Office & Furniture", "Administration", "Council Hall Level 3", 180000.0, "Featherlite Furniture", "Featherlite Care", False),
        ("Godrej Defender Aurum Safe 4-Drawer Fireproof", "Office & Furniture", "Administration", "Controller of Examinations Vault", 145000.0, "Godrej Security Solutions", "Godrej Safe AMC", False),
        ("Steel Library Bookcase Double-Sided 6-Tier Bay 1", "Office & Furniture", "Central Library", "Library Stacks Floor 1", 38000.0, "Godrej Storage Solutions", "", False),
        ("Steel Library Bookcase Double-Sided 6-Tier Bay 2", "Office & Furniture", "Central Library", "Library Stacks Floor 1", 38000.0, "Godrej Storage Solutions", "", False),
        ("Steel Library Bookcase Double-Sided 6-Tier Bay 3", "Office & Furniture", "Central Library", "Library Stacks Floor 2", 38000.0, "Godrej Storage Solutions", "", False),
        ("Steel Library Bookcase Double-Sided 6-Tier Bay 4", "Office & Furniture", "Central Library", "Library Stacks Floor 2", 38000.0, "Godrej Storage Solutions", "", False),
        ("Clarus Magnetic Glassboard 6x4 ft Mobile Partition", "Office & Furniture", "Computer Science", "Ideation Studio Room 310", 39000.0, "Clarus Glassboards", "", True),
        ("Clarus Magnetic Glassboard 6x4 ft Mobile Partition #2", "Office & Furniture", "Architecture & Planning", "Critique Room 402", 39000.0, "Clarus Glassboards", "", True),
        ("Featherlite Contact High-Back Executive Chair", "Office & Furniture", "Administration", "Dean Academics Office", 22000.0, "Featherlite Furniture", "", False),
        ("Featherlite Contact High-Back Executive Chair #2", "Office & Furniture", "Administration", "Dean Student Affairs Office", 22000.0, "Featherlite Furniture", "", False),
        ("Heavy Duty Fire-Resistant Filing Cabinet (4-Drawer)", "Office & Furniture", "Administration", "HR & Faculty Records Room", 34000.0, "Godrej Interio", "", False),
        ("Heavy Duty Fire-Resistant Filing Cabinet (4-Drawer) #2", "Office & Furniture", "Administration", "Finance & Accounts Strongroom", 34000.0, "Godrej Interio", "", False),
        ("Study Carrels with Acoustic Dividers (Set of 6)", "Office & Furniture", "Central Library", "Library Quiet Zone Floor 3", 58000.0, "Methodex Systems", "", False),
        ("Drafting Tables with Hydraulic Height Adjust (Set of 8)", "Office & Furniture", "Architecture & Planning", "Studio Hall 1", 112000.0, "Universal Drafting Systems", "", False),
        ("Dormitory Bunk Beds Heavy Duty Steel (Set of 10)", "Office & Furniture", "Administration", "Hostel Block A Linen & Furniture Store", 140000.0, "Geeken Seating", "", False),
        ("Auditorium Cushioned Tip-Up Seats (Row A 1-20)", "Office & Furniture", "Administration", "Auditorium Main Floor", 120000.0, "Penworker Seating", "Auditorium AMC", False),
        ("Cafeteria Dining Table Stainless Steel 6-Seater #1", "Office & Furniture", "Administration", "Central Student Dining Hall", 28000.0, "Neelkamal Commercial", "", False),
        ("Cafeteria Dining Table Stainless Steel 6-Seater #2", "Office & Furniture", "Administration", "Central Student Dining Hall", 28000.0, "Neelkamal Commercial", "", False),
        ("Medical Centre Examination Couch with Paper Dispenser", "Office & Furniture", "Medical & Health Centre", "Doctor Consultation Room 1", 18000.0, "Janak Healthcare", "", False),
        ("Medical Centre Observation Bed with Side Rails", "Office & Furniture", "Medical & Health Centre", "Recovery Ward Bed 1", 24000.0, "Janak Healthcare", "", False),

        # --- Network Infrastructure (25 items) ---
        ("Cisco Catalyst 9300 48-Port PoE+ Core Switch", "Network Infrastructure", "Campus IT Services", "Server Room Rack 1 · Unit 14", 320000.0, "Cisco Systems India", "Cisco Smart Net Total Care", False),
        ("Cisco Catalyst 9300 48-Port PoE+ Core Switch #2", "Network Infrastructure", "Campus IT Services", "Server Room Rack 2 · Unit 14", 320000.0, "Cisco Systems India", "Cisco Smart Net Total Care", False),
        ("Aruba CX 6300M 24-Port SFP+ Aggregation Switch", "Network Infrastructure", "Campus IT Services", "Data Centre Core Rack", 290000.0, "Aruba Networks (HPE)", "Aruba Care Essential", False),
        ("Cisco Catalyst 9120AX Wi-Fi 6 Access Point (Turing)", "Network Infrastructure", "Campus IT Services", "Turing Block Ceiling Floor 2", 34000.0, "Cisco Systems India", "Cisco Smart Net Total Care", False),
        ("Cisco Catalyst 9120AX Wi-Fi 6 Access Point (Newton)", "Network Infrastructure", "Campus IT Services", "Newton Block Ceiling Floor 1", 34000.0, "Cisco Systems India", "Cisco Smart Net Total Care", False),
        ("Cisco Catalyst 9120AX Wi-Fi 6 Access Point (Library)", "Network Infrastructure", "Central Library", "Library Central Atrium Ceiling", 34000.0, "Cisco Systems India", "Cisco Smart Net Total Care", False),
        ("Aruba AP-535 Dual-Radio Wi-Fi 6 Access Point (Hostel)", "Network Infrastructure", "Campus IT Services", "Hostel Cluster Gate Access Point", 38000.0, "Aruba Networks (HPE)", "Aruba Care Essential", False),
        ("Fortinet FortiGate 100F Enterprise Firewall", "Network Infrastructure", "Campus IT Services", "Campus Perimeter Gateway Rack", 280000.0, "Fortinet India", "FortiCare 24x7 3Y", False),
        ("Palo Alto Networks PA-440 Next-Gen Firewall", "Network Infrastructure", "Campus IT Services", "Research DMZ Rack", 220000.0, "Palo Alto Networks", "PAN-OS Platinum Support", False),
        ("Cisco 4331 Integrated Services Edge Router", "Network Infrastructure", "Campus IT Services", "WAN Demarcation Room", 160000.0, "Cisco Systems India", "Cisco Smart Net Total Care", False),
        ("MikroTik Cloud Core Router CCR2004-16G-2S+", "Network Infrastructure", "Computer Science", "Computer Science Network Lab", 54000.0, "MikroTik SIA", "", False),
        ("APC NetShelter SX 42U Server Rack Enclosure #1", "Network Infrastructure", "Campus IT Services", "Campus Data Centre Row A", 125000.0, "Schneider Electric India", "APC Maintenance", False),
        ("APC NetShelter SX 42U Server Rack Enclosure #2", "Network Infrastructure", "Campus IT Services", "Campus Data Centre Row A", 125000.0, "Schneider Electric India", "APC Maintenance", False),
        ("APC Smart-UPS RT 10kVA On-Line UPS with Batt Bank", "Network Infrastructure", "Campus IT Services", "Data Centre UPS Room", 340000.0, "Schneider Electric India", "APC Onsite 24x7 AMC", False),
        ("Eaton 9PX 6kVA Rackmount Online UPS", "Network Infrastructure", "Computer Science", "Turing Block Rack Room 3", 195000.0, "Eaton Power Quality", "Eaton Service Plan", False),
        ("Synology RackStation RS3621xs+ NAS (96TB)", "Network Infrastructure", "Campus IT Services", "Campus Central Backup Vault", 490000.0, "Synology Inc", "Synology Extended Pro", False),
        ("QNAP TS-1683XU-RP Enterprise Storage Server (64TB)", "Network Infrastructure", "Computer Science", "AI & Big Data Cluster Rack", 440000.0, "QNAP Systems", "QNAP Advanced Care", False),
        ("Ubiquiti UniFi Dream Machine Special Edition (UDM-SE)", "Network Infrastructure", "Sports", "Sports Complex Admin Office", 46000.0, "Ubiquiti Networks", "", False),
        ("Netgear ProSAFE 24-Port Gigabit Smart Managed Switch", "Network Infrastructure", "Civil", "Civil Structural Sensor Hub", 28000.0, "Netgear India", "", False),
        ("Fluke Networks LinkIQ Cable+Network Tester", "Network Infrastructure", "Campus IT Services", "Field IT Tech Toolbag", 195000.0, "Fluke Networks", "Fluke Gold Support", True),
        ("Fluke MicroScanner MS2-100 Cable Verifier", "Network Infrastructure", "Campus IT Services", "Campus IT Tech Workbench", 54000.0, "Fluke Networks", "", True),
        ("StarTech 1U Rackmount KVM Console with 17\" LCD", "Network Infrastructure", "Campus IT Services", "Data Centre Console 1", 62000.0, "StarTech.com", "", False),
        ("PDU Metered Rack Power Strip (APC AP7821)", "Network Infrastructure", "Campus IT Services", "Data Centre Rack 1 PDU A", 28000.0, "Schneider Electric India", "", False),
        ("PDU Metered Rack Power Strip (APC AP7821) #2", "Network Infrastructure", "Campus IT Services", "Data Centre Rack 1 PDU B", 28000.0, "Schneider Electric India", "", False),
        ("Patch Panel 48-Port Cat6A Shielded (CommScope)", "Network Infrastructure", "Campus IT Services", "Server Room Main Distribution", 18000.0, "CommScope Enterprise", "", False),

        # --- Medical & Safety (15 items) ---
        ("Philips HeartStart FRx AED Defibrillator #1", "Medical & Safety", "Medical & Health Centre", "Sports Complex Entry Foyer Wall", 145000.0, "Philips Healthcare", "Philips AED Annual Check", True),
        ("Philips HeartStart FRx AED Defibrillator #2", "Medical & Safety", "Administration", "Admin Block Ground Lobby Wall", 145000.0, "Philips Healthcare", "Philips AED Annual Check", True),
        ("Zoll AED 3 Fully Automatic Defibrillator", "Medical & Safety", "Central Library", "Library Level 1 Information Desk", 168000.0, "Zoll Medical India", "Zoll Care Plan", True),
        ("Speakman Traditional Eye Wash & Drench Shower Unit", "Medical & Safety", "Chemistry & Life Sciences", "Chemical Synthesis Lab Corridor", 68000.0, "Speakman Company", "Plumbing & Safety Audit", False),
        ("Speakman Pedestal Mount Eye Wash Station", "Medical & Safety", "Biotechnology", "BioTech Wing Level 2 Airlock", 42000.0, "Speakman Company", "Plumbing & Safety Audit", False),
        ("Honeywell BW Ultra 5-Gas Portable Atmospheric Monitor", "Medical & Safety", "Civil", "Underground Utility & Sump Inspection", 125000.0, "Honeywell Industrial Safety", "Honeywell Sensor Calibration", True),
        ("Industrial First Aid & Trauma Response Wall Cabinet #1", "Medical & Safety", "Mechanical", "Mechanical Workshop First Aid Point", 14000.0, "St John Ambulance India", "Quarterly Restock Plan", False),
        ("Industrial First Aid & Trauma Response Wall Cabinet #2", "Medical & Safety", "Civil", "Civil Heavy Structures Shed", 14000.0, "St John Ambulance India", "Quarterly Restock Plan", False),
        ("Welch Allyn Connex Spot Vital Signs Monitor", "Medical & Safety", "Medical & Health Centre", "Triage Room 1", 185000.0, "Baxter Healthcare (Welch Allyn)", "Welch Allyn Biomedical AMC", True),
        ("Mindray DP-10 Digital Ultrasonic Diagnostic System", "Medical & Safety", "Medical & Health Centre", "Health Centre Ultrasound Room", 240000.0, "Mindray Medical India", "Mindray Biomedical Service", False),
        ("Fire Suppression Clean Agent FM-200 45kg Cylinder", "Medical & Safety", "Campus IT Services", "Campus Server Room Ceiling", 280000.0, "Minimax Fire Protection", "Fire Safety Compliance AMC", False),
        ("Ceasefire CO2 Fire Extinguisher 4.5kg (Turing)", "Medical & Safety", "Computer Science", "Turing Block Corridor Floor 2", 9500.0, "Ceasefire Industries", "Annual Refill AMC", False),
        ("Ceasefire ABC Dry Powder Extinguisher 6kg (Admin)", "Medical & Safety", "Administration", "Admin Wing Floor 1", 6500.0, "Ceasefire Industries", "Annual Refill AMC", False),
        ("Wall-Mounted Digital Infrared Body Temp Scanner Kiosk", "Medical & Safety", "Medical & Health Centre", "Campus Main Turnstile Entrance", 18000.0, "Hikvision Security", "", False),
        ("Stretcher Trolley Stainless Steel with IV Pole", "Medical & Safety", "Medical & Health Centre", "Health Centre Emergency Bay", 26000.0, "Janak Healthcare", "", True),
    ]

    holders_pool = [
        "Dr. Maya Iyer", "Dr. Priya Ramesh", "Arjun Menon", "Rohan Kapoor", "Dr. Rajesh Sharma",
        "Dr. Amit Verma", "Dr. Sunita Rao", "Dr. Meera Nambiar", "Manish Kulkarni", "Prof. Anita Sen",
        "Geeta Paul", "Kavita Deshmukh", "Suresh Nair", "Dr. Deepak Joshi", "Tarun Bhatia",
        "Ananya Rao", "Karan Patel", "Sara Thomas", "Divya Krishnan"
    ]
    
    # 5 Statuses: Available (~44%), Allocated (~34%), Under Maintenance (~12%), Lost (~5%), Retired (~5%)
    status_cycle = (
        ["Available"] * 10 +
        ["Allocated"] * 8 +
        ["Under Maintenance"] * 3 +
        ["Lost"] * 1 +
        ["Retired"] * 1
    ) # 23-pattern repeats smoothly

    tag_counter = 1006
    for i, item in enumerate(catalog):
        name, cat, dept, loc, cost, supp, amc, bookable = item
        st = status_cycle[i % len(status_cycle)]
        holder = holders_pool[i % len(holders_pool)] if st == "Allocated" else None
        ret_date = days_ahead(7 + (i % 25)) if st == "Allocated" else None
        
        # Staggered purchase dates across 2022 - 2025
        p_offset = 120 + (i * 11) % 900
        p_date = day_str(-p_offset)
        w_offset = 365 + (i * 17) % 750
        w_date = day_str(-p_offset + w_offset)
        
        aid = f"ast_cat_{i+1:03d}"
        tag = f"AF-2025-{tag_counter}"
        tag_counter += 1
        sn = f"SN-{cat[:3].upper()}-{10000 + i*37}"
        
        assets.append({
            "asset_id": aid,
            "tag": tag,
            "name": name,
            "category": cat,
            "location": loc,
            "department": dept,
            "status": st,
            "holder": holder,
            "expected_return_at": ret_date,
            "serial": sn,
            "bookable": bookable,
            "purchase_cost": cost,
            "purchase_date": p_date,
            "warranty_end": w_date,
            "supplier": supp,
            "amc_provider": amc,
            "notes": f"Standard inventory record for {name}. Verified in regular cycle.",
            "updated_at": days_ago(i % 15, hours=(i*3)%24),
            "created_at": days_ago(p_offset),
        })

    return assets

# ==============================================================================
# Helper to build 50 Maintenance Work Orders
# ==============================================================================
def generate_maintenance(assets):
    # Statuses: Pending (12), Approved (10), In progress (12), Resolved (11), Rejected (5)
    # Priorities: High (18), Medium (20), Low (12)
    m_list = []
    
    # 5 Anchor maintenance records
    anchors = [
        ("mnt_seed_01", "ast_seed_2", "Spindle vibration during high RPM calibration test", "High", "Arjun Menon", "user_demo_arjun", "In progress", None, None),
        ("mnt_demo_open", "ast_demo_proj1", "Projector optical engine lamp flickering during lectures", "Medium", "Dr. Priya Ramesh", "user_demo_priya", "Pending", None, None),
        ("mnt_demo_prog", "ast_seed_0", "Oscilloscope probe attenuation drift on Channel 2", "High", "Arjun Menon", "user_demo_arjun", "In progress", None, None),
        ("mnt_demo_res", "ast_demo_room1", "Air conditioning thermostat not cooling in Seminar Hall A", "Low", "Maya Iyer", "user_demo_assetflow", "Resolved", days_ago(4), None),
        ("mnt_demo_rej", "ast_seed_3", "Request for unapproved filament color upgrade and extruder modification", "Low", "Manish Kulkarni", "user_emp_manish", "Rejected", None, days_ago(6)),
    ]
    
    for rid, aid, desc, prio, by, by_id, st, res_at, rej_at in anchors:
        m_list.append({
            "request_id": rid,
            "asset_id": aid,
            "description": desc,
            "priority": prio,
            "category": "Calibration",
            "location": "Campus Central",
            "reporter_contact": "+91 98201 40001",
            "raised_by": by,
            "raised_by_id": by_id,
            "status": st,
            "photos": [
                {"public_id": "assetflow/maintenance/sample_1", "url": "https://res.cloudinary.com/ifvlp2sb/image/upload/v1723100000/sample_tool.jpg", "uploaded_by": by, "uploaded_at": days_ago(3)}
            ] if st in ["In progress", "Resolved"] else [],
            "created_at": days_ago(12),
            "resolved_at": res_at,
            "rejected_at": rej_at,
        })
        
    descriptions = [
        ("Centrifuge rotor unbalanced vibration warning during 8000 RPM cycle", "High", "Mechanical", "Biotechnology"),
        ("Projector HDMI port 2 loose connection and signal cutoff", "Medium", "Electrical", "Computer Science"),
        ("CNC coolant pump leakage and low pressure cutoff error code E-14", "High", "Mechanical", "Mechanical"),
        ("Oscilloscope Channel 1 intermittent ground hum and noise spike", "Medium", "Electrical", "Electronics & Communication"),
        ("Hydraulic press pressure sensor reading 15% lower than master gauge", "High", "Mechanical", "Mechanical"),
        ("Central Library AC unit blower motor emitting bearing screech", "Low", "HVAC", "Central Library"),
        ("UV-Vis Spectrophotometer tungsten lamp failed ignition", "High", "Optics", "Chemistry & Life Sciences"),
        ("College Bus #1 brake pad wear indicator blinking on dashboard", "High", "Mechanical", "Administration"),
        ("College Bus #2 power steering fluid seepage near reservoir", "Medium", "Mechanical", "Administration"),
        ("3D Printer heated bed thermistor open circuit error during warmup", "High", "Electrical", "Computer Science"),
        ("Core Switch 1 fan tray 2 speed below normal threshold", "High", "Network", "Campus IT Services"),
        ("Digital multimeter calibration certificate expiring; zero-offset check needed", "Low", "Calibration", "Electrical & Electronics"),
        ("Woodworking table saw safety brake cartridge indicator amber", "High", "Mechanical", "Architecture & Planning"),
        ("DSLR camera sensor cleaning required due to visible dust spot at f/8", "Low", "Optics", "Media & Communications"),
        ("AED Unit 1 internal self-test battery chirp heard in sports foyer", "High", "Electrical", "Medical & Health Centre"),
        ("Wireless mic receiver antenna B loose connector nut", "Low", "Electronics", "Media & Communications"),
        ("HPLC flow rate fluctuation due to air bubble in purge valve", "High", "Chemical", "Chemistry & Life Sciences"),
        ("Universal Testing Machine emergency stop button sticking", "High", "Safety", "Civil"),
        ("Compression testing machine load cell zero-drift after heavy pour test", "Medium", "Civil", "Civil"),
        ("Smart board touch digitizer dead spot on bottom-right corner", "Medium", "IT Equipment", "Administration"),
        ("Podcast audio console channel 4 fader crackle during broadcast", "Low", "Audio", "Media & Communications"),
        ("Gas detector O2 sensor requires 180-day recalibration bump test", "Medium", "Safety", "Civil"),
        ("Microscope stage vertical adjustment rack skipping gear teeth", "Medium", "Optics", "Biotechnology"),
        ("Campus shuttle van front tire sidewall abrasion noticed during pre-trip", "High", "Mechanical", "Administration"),
        ("Laser cutter chiller water temperature warning alarm (over 24C)", "High", "HVAC", "Architecture & Planning"),
        ("Biosafety cabinet HEPA filter differential pressure gauge red-line", "High", "Environmental", "Biotechnology"),
        ("Workstation Tower power supply fan loud buzzing on boot", "Low", "Hardware", "Computer Science"),
        ("Treadmill motor belt tension slip at speeds above 8 km/h", "Medium", "Sports Gear", "Sports"),
        ("Sub-station UPS battery bank cell 14 terminal oxidation detected", "High", "Electrical", "Campus IT Services"),
        ("Cleanroom air shower interlock door sensor not engaging magnet", "High", "Structural", "Biotechnology"),
        ("Concrete core drill bit water jacket seal ring tear", "Medium", "Civil", "Civil"),
        ("Tennis court ball machine wheel rubber glaze causing erratic feed", "Low", "Sports Gear", "Sports"),
        ("Document camera flexible gooseneck arm sagging under camera head weight", "Low", "Hardware", "Chemistry & Life Sciences"),
        ("Heavy duty guillotine shear hydraulic valve spool sticking", "High", "Hydraulics", "Mechanical"),
        ("Band saw blade tension gauge reading unreliable; blade slipped twice", "High", "Mechanical", "Mechanical"),
        ("Interactive display stylus pen battery contact corroded", "Low", "IT Equipment", "Computer Science"),
        ("Server Room APC In-Row cooler condensate drainage tray overflow alert", "High", "HVAC", "Campus IT Services"),
        ("Survey Total Station tripod clamp lever cracked during field transit", "Medium", "Civil", "Civil"),
        ("Campus EV van onboard charge controller throwing error code OBC-03", "High", "Electrical", "Administration"),
        ("First aid eye wash station pressure booster valve dripping continuously", "Low", "Plumbing", "Chemistry & Life Sciences"),
        ("Studio Aputure 200d light cooling fan rattling at full brightness", "Low", "Optics", "Media & Communications"),
        ("Network firewall secondary power supply unit failed PSU self-test", "High", "Network", "Campus IT Services"),
        ("Gym workout cable cross pulley wheel cable fraying detected", "High", "Sports Gear", "Sports"),
        ("Centrifuge safety lid emergency release cable jammed", "High", "Mechanical", "Biotechnology"),
        ("Colchester lathe carriage power feed lever slipping out of gear", "Medium", "Mechanical", "Mechanical"),
    ]

    target_assets = [a for a in assets if a["asset_id"] not in ["ast_seed_0", "ast_seed_2", "ast_demo_proj1", "ast_demo_room1", "ast_seed_3"]]
    statuses_sequence = (
        ["Pending"] * 11 +
        ["Approved"] * 9 +
        ["In progress"] * 10 +
        ["Resolved"] * 10 +
        ["Rejected"] * 4
    ) # 44 items
    
    reporters = [
        ("Arjun Menon", "user_demo_arjun"),
        ("Dr. Priya Ramesh", "user_demo_priya"),
        ("Manish Kulkarni", "user_emp_manish"),
        ("Rahul Pillai", "user_emp_rahul"),
        ("Prof. Anita Sen", "user_emp_anita"),
        ("Geeta Paul", "user_emp_geeta"),
        ("Tarun Bhatia", "user_emp_tarun"),
        ("Dr. Rajesh Sharma", "user_hod_rajesh"),
        ("Suresh Nair", "user_mgr_suresh"),
        ("Ananya Rao", "user_demo_ananya"),
    ]

    for i in range(len(descriptions)):
        desc, prio, cat_tag, dept_tag = descriptions[i]
        st = statuses_sequence[i % len(statuses_sequence)]
        rep_name, rep_id = reporters[i % len(reporters)]
        ast = target_assets[i % len(target_assets)]
        
        c_days = 2 + (i % 22)
        created_at = days_ago(c_days, hours=(i*2)%24)
        res_at = days_ago(max(1, c_days - 3)) if st == "Resolved" else None
        rej_at = days_ago(max(1, c_days - 2)) if st == "Rejected" else None
        
        rid = f"mnt_ticket_{i+1:03d}"
        
        m_list.append({
            "request_id": rid,
            "asset_id": ast["asset_id"],
            "description": desc,
            "priority": prio,
            "category": cat_tag,
            "location": ast["location"],
            "reporter_contact": f"+91 98201 {40000 + (i%99):04d}",
            "raised_by": rep_name,
            "raised_by_id": rep_id,
            "status": st,
            "photos": [],
            "created_at": created_at,
            "resolved_at": res_at,
            "rejected_at": rej_at,
        })
        
    return m_list

# ==============================================================================
# Helper to build 55 Bookings
# ==============================================================================
def generate_bookings(assets):
    bookable_assets = [a for a in assets if a.get("bookable")]
    b_list = []
    
    # Anchor bookings
    anchors = [
        ("laptop1", "ast_demo_laptop1", "Dell Latitude 5540 Laptop", "Turing Block · Floor 3", "IT Equipment", 0, "09:00", "11:00", "Sprint demo & quarterly retrospective", "Team Retro", "Computer Science", 10, "Dr. Priya Ramesh", "user_demo_priya", "Confirmed"),
        ("room1", "ast_demo_room1", "Seminar Hall A", "Academic Block · Floor 2", "Room", 1, "11:00", "13:30", "Distinguished guest lecture — Agentic AI & Robotics", "Guest Lecture — AI", "Computer Science", 120, "Dr. Priya Ramesh", "user_demo_priya", "Confirmed"),
        ("room2", "ast_demo_room2", "Conference Room B", "Admin Block · Floor 1", "Room", 2, "14:00", "16:00", "Executive academic council budget review", "Budget Review", "Administration", 18, "Rohan Kapoor", "user_demo_admin", "Confirmed"),
        ("proj1", "ast_demo_proj1", "Epson Projector EB-X06 (AV Store)", "Administration · AV Store", "IT Equipment", 3, "10:00", "12:00", "NBA accreditation documentation photo shoot", "Accreditation Prep", "Administration", 6, "Maya Iyer", "user_demo_assetflow", "Confirmed"),
        ("bus1", "ast_demo_vehicle1", "College Bus #1 (32-seater)", "Transport Bay · Bay 1", "Vehicle", 4, "07:00", "18:00", "Industrial plant visit to Heavy Forge Machinery", "Industrial Visit", "Mechanical", 32, "Arjun Menon", "user_demo_arjun", "Confirmed"),
    ]
    
    for key, rid, rname, loc, cat, offset, st, et, purpose, title, dept, att, by, by_id, status in anchors:
        b_list.append({
            "booking_id": f"book_demo_{key}",
            "resource_id": rid,
            "resource_name": rname,
            "location": loc,
            "category": cat,
            "date": day_str(offset),
            "start_time": st,
            "end_time": et,
            "purpose": purpose,
            "event_title": title,
            "department": dept,
            "attendees": att,
            "contact": "+91 98201 10001",
            "requested_by": by,
            "requested_by_id": by_id,
            "status": status,
            "created_at": days_ago(5),
        })

    booking_scenarios = [
        # (title, purpose, dept, attendees, start, end, day_offset, status)
        # Past 5 days (Done)
        ("Alumni Interaction Session", "Sharing civil industry experiences with final year batch", "Civil", 45, "10:00", "12:00", -4, "Confirmed"),
        ("Machine Tool Hands-on Lab", "Practical lathe turning & spindle training session", "Mechanical", 25, "14:00", "17:00", -3, "Confirmed"),
        ("Robotics Scrimmage Match", "Inter-college autonomous line follower scrimmage", "Computer Science", 60, "11:00", "14:00", -3, "Confirmed"),
        ("Placement Mock Interviews", "HR mock interview rounds for pre-final students", "Administration", 30, "09:00", "13:00", -2, "Confirmed"),
        ("Biotech Cell Culture Workshop", "Hands-on cryogenic cell preservation demonstration", "Biotechnology", 20, "10:00", "12:30", -2, "Confirmed"),
        ("Architecture Model Exhibition", "Jury review of urban housing sustainable models", "Architecture & Planning", 80, "13:00", "17:00", -1, "Confirmed"),
        ("Cricket Inter-Department Friendly", "Mechanical vs Computer Science staff cricket fixture", "Sports", 28, "15:00", "18:30", -1, "Confirmed"),
        ("Campus Safety Drill Coordination", "Meeting of building wardens and fire safety leads", "Administration", 15, "09:30", "11:00", -1, "Confirmed"),
        ("Cancelled Vendor Tech Talk", "Cancelled due to speaker travel delay", "Electronics & Communication", 50, "14:00", "16:00", -1, "Cancelled"),
        ("Cancelled Equipment Calibration Slot", "Rescheduled due to power maintenance window", "Electrical & Electronics", 8, "10:00", "12:00", -2, "Cancelled"),

        # Today (day 0)
        ("Morning HOD Coordination Meet", "Weekly academic progress and attendance review", "Administration", 16, "09:00", "10:30", 0, "Confirmed"),
        ("3D Printing Prototyping Workshop", "Rapid manufacturing of drone chassis arms", "Mechanical", 15, "11:00", "13:00", 0, "Confirmed"),
        ("Media Cell Student Podcast Shoot", "Interviewing national hackathon winning team", "Media & Communications", 4, "13:30", "15:30", 0, "Confirmed"),
        ("Badminton Inter-College Selection", "Varsity trials for upcoming zonal tournament", "Sports", 35, "16:00", "19:00", 0, "Confirmed"),

        # Next 1 to 6 days (Upcoming agenda)
        ("VLSI Chip Design Seminar", "Keynote on FinFET and 2nm architecture evolution", "Electronics & Communication", 95, "09:30", "12:00", 1, "Confirmed"),
        ("Field Geology Soil Sampling Trip", "Geotechnical site visit to quarry excavation basin", "Civil", 24, "08:00", "16:00", 1, "Confirmed"),
        ("Faculty Research Paper Defense", "Doctoral defense on nanomaterials energy storage", "Physics & Materials", 30, "14:00", "16:30", 1, "Confirmed"),
        ("Campus Bus Transit to Metro Station", "Special student shuttle service for evening exams", "Administration", 45, "17:00", "19:00", 1, "Confirmed"),
        
        ("NBA Peer Review Rehearsal", "Departmental presentation walkthrough for accreditation", "Computer Science", 40, "10:00", "12:30", 2, "Confirmed"),
        ("Campus Shutter Photography Walk", "Student photo club macro photography session", "Media & Communications", 18, "07:00", "09:30", 2, "Confirmed"),
        ("Sports Conditioning Camp", "Fitness screening and VO2 max measurements", "Sports", 30, "16:00", "18:00", 2, "Confirmed"),
        ("Cancelled Hall Reservation", "Duplicate booking cancelled by organiser", "Administration", 10, "14:00", "15:00", 2, "Cancelled"),

        ("Hackathon 24-Hour Kickoff", "Statewide Smart Campus Hackathon Opening Ceremony", "Computer Science", 220, "09:00", "11:30", 3, "Confirmed"),
        ("High-Performance Computing Demo", "GPU cluster workload orchestration masterclass", "Computer Science", 50, "14:00", "16:00", 3, "Confirmed"),
        ("Chemistry Chromatography Practicum", "Hands-on HPLC extraction separation run", "Chemistry & Life Sciences", 16, "11:00", "13:30", 3, "Confirmed"),

        ("Library Book Fair & Exhibition", "Annual publisher showcase and academic discount fair", "Central Library", 150, "09:00", "17:00", 4, "Confirmed"),
        ("Industrial Automation PLC Lab", "Siemens S7-1200 PLC ladder logic programming session", "Electrical & Electronics", 30, "11:00", "13:00", 4, "Confirmed"),
        ("Campus Electric Bus Route Trial", "Green transport zero-emission intra-campus route check", "Administration", 14, "14:00", "16:00", 4, "Confirmed"),

        ("Drone Mapping & Photogrammetry", "Aerial surveying of new academic hostel construction", "Civil", 12, "08:30", "11:30", 5, "Confirmed"),
        ("Table Tennis Zonal Championships", "Inter-collegiate tournament preliminary heats", "Sports", 65, "10:00", "16:00", 5, "Confirmed"),
        ("Blood Donation Camp Hub", "Annual Red Cross volunteer drive and health screening", "Medical & Health Centre", 180, "09:00", "15:00", 5, "Confirmed"),

        ("Weekend Robotics Coding Jam", "ROS2 navigation stack debugging marathon", "Computer Science", 35, "10:00", "18:00", 6, "Confirmed"),
        ("Music & Drama Club Rehearsal", "Annual cultural fest stage blocking and acoustic tuning", "Administration", 40, "13:00", "17:00", 6, "Confirmed"),
        ("Tennis Coaching Clinic", "Serving technique and backhand stroke masterclass", "Sports", 20, "16:30", "18:30", 6, "Confirmed"),

        # Next week (Day 7 - 12)
        ("International Symposium on Green Tech", "Opening plenary and panel discussions", "Civil", 180, "09:00", "17:00", 7, "Confirmed"),
        ("Campus Bus Shuttle — Zonal Sports", "Transporting varsity team to University Stadium", "Sports", 50, "06:30", "19:00", 7, "Confirmed"),
        ("Biotechnology Bioethics Debate", "Panel discussion on CRISPR therapeutics governance", "Biotechnology", 85, "11:00", "13:00", 8, "Confirmed"),
        ("Executive Leadership Strategy Meet", "Ten-year campus master plan infrastructure roadmap", "Administration", 15, "14:00", "17:30", 9, "Confirmed"),
        ("Clean Energy Vehicle Showcase", "SAE student formula electric racing car unveil", "Mechanical", 110, "15:00", "17:00", 10, "Confirmed"),
        ("Central Library Advisory Committee", "Quarterly journal subscription and e-database review", "Central Library", 12, "11:00", "13:00", 11, "Confirmed"),
    ]

    req_users = [
        ("Dr. Priya Ramesh", "user_demo_priya"),
        ("Rohan Kapoor", "user_demo_admin"),
        ("Arjun Menon", "user_demo_arjun"),
        ("Maya Iyer", "user_demo_assetflow"),
        ("Dr. Rajesh Sharma", "user_hod_rajesh"),
        ("Dr. Amit Verma", "user_hod_amit"),
        ("Coach Vikram Rathore", "user_hod_vikram"),
        ("Dr. Meera Nambiar", "user_hod_meera"),
        ("Dr. Deepak Joshi", "user_hod_deepak"),
        ("Geeta Paul", "user_emp_geeta"),
        ("Ananya Rao", "user_demo_ananya"),
        ("Karan Patel", "user_stu_karan"),
    ]

    for i, scen in enumerate(booking_scenarios):
        title, purp, dept, att, st, et, offset, b_status = scen
        res = bookable_assets[i % len(bookable_assets)]
        by_name, by_id = req_users[i % len(req_users)]
        
        bid = f"book_slot_{i+1:03d}"
        b_list.append({
            "booking_id": bid,
            "resource_id": res["asset_id"],
            "resource_name": res["name"],
            "location": res["location"],
            "category": res["category"],
            "date": day_str(offset),
            "start_time": st,
            "end_time": et,
            "purpose": purp,
            "event_title": title,
            "department": dept,
            "attendees": att,
            "contact": f"+91 98201 {30000 + i:04d}",
            "requested_by": by_name,
            "requested_by_id": by_id,
            "status": b_status,
            "created_at": days_ago(abs(offset) + 3),
        })

    return b_list

# ==============================================================================
# Helper to build 12 Audits
# ==============================================================================
def generate_audits(assets):
    audits = []
    
    # Anchor closed audit
    cs_assets = [a for a in assets if a["department"] == "Computer Science"][:15]
    audits.append({
        "audit_id": "audit_demo_closed",
        "department": "Computer Science",
        "period": "July 2026",
        "auditors": ["Maya Iyer", "Dr. Priya Ramesh"],
        "status": "Closed",
        "created_at": days_ago(45),
        "closed_at": days_ago(38),
        "items": [
            {
                "asset_id": a["asset_id"],
                "tag": a["tag"],
                "name": a["name"],
                "expected_location": a["location"],
                "verification": "Verified" if idx % 4 != 3 else "Damaged",
                "note": "Verified physically on lab bench" if idx % 4 != 3 else "Minor casing crack noted",
                "photos": [
                    {"public_id": f"assetflow/audits/audit_demo_closed/{a['asset_id']}/p1", "url": "https://res.cloudinary.com/ifvlp2sb/image/upload/v1723100000/sample_tool.jpg", "uploaded_by": "Maya Iyer", "uploaded_at": days_ago(40)}
                ] if idx in [0, 2, 4] else []
            }
            for idx, a in enumerate(cs_assets)
        ]
    })

    # Additional audit cycles across departments
    configs = [
        ("audit_cs_aug2026", "Computer Science", "August 2026", ["Maya Iyer", "Manish Kulkarni"], "Open", 20, None),
        ("audit_mech_aug2026", "Mechanical", "August 2026", ["Arjun Menon", "Dr. Rajesh Sharma"], "Open", 18, None),
        ("audit_lib_jul2026", "Central Library", "July 2026", ["Dr. Meera Nambiar"], "Open", 15, None),
        ("audit_ee_aug2026", "Electrical & Electronics", "August 2026", ["Prof. Anita Sen", "Dr. Sunita Rao"], "Open", 14, None),
        ("audit_sports_sep2026", "Sports", "September 2026", ["Coach Vikram Rathore"], "Open", 12, None),
        ("audit_admin_q2", "Administration", "Q2 2026", ["Rohan Kapoor", "Suresh Nair"], "Closed", 60, 52),
        ("audit_civil_q1", "Civil", "Q1 2026", ["Dr. Amit Verma"], "Closed", 90, 82),
        ("audit_it_annual", "Campus IT Services", "Annual 2025-26", ["Kavita Deshmukh", "Tarun Bhatia"], "Closed", 110, 102),
        ("audit_biotech_jun2026", "Biotechnology", "June 2026", ["Dr. Deepak Joshi"], "Closed", 75, 68),
        ("audit_mech_q2", "Mechanical", "Q2 2026", ["Dr. Rajesh Sharma"], "Closed", 85, 78),
        ("audit_media_may2026", "Media & Communications", "May 2026", ["Geeta Paul"], "Closed", 100, 94),
    ]

    for aid, dept, period, auditors, status, created_offset, closed_offset in configs:
        dept_assets = [a for a in assets if a["department"] == dept][:14]
        items = []
        for i, a in enumerate(dept_assets):
            if status == "Open":
                # Mix of Verified, Pending, Missing, Damaged
                v_options = ["Verified", "Verified", "Pending", "Missing", "Damaged"]
                v_choice = v_options[i % len(v_options)]
            else:
                v_options = ["Verified", "Verified", "Verified", "Damaged", "Verified"]
                v_choice = v_options[i % len(v_options)]
                
            items.append({
                "asset_id": a["asset_id"],
                "tag": a["tag"],
                "name": a["name"],
                "expected_location": a["location"],
                "verification": v_choice,
                "note": f"Audited per protocol by {auditors[0]}." if v_choice == "Verified" else ("Physical tag unreadable" if v_choice == "Damaged" else ("Asset not found in room" if v_choice == "Missing" else "")),
                "photos": [
                    {"public_id": f"assetflow/audits/{aid}/{a['asset_id']}/audit_p", "url": "https://res.cloudinary.com/ifvlp2sb/image/upload/v1723100000/sample_tool.jpg", "uploaded_by": auditors[0], "uploaded_at": days_ago(created_offset - 1)}
                ] if i % 4 == 0 else []
            })
            
        audits.append({
            "audit_id": aid,
            "department": dept,
            "period": period,
            "auditors": auditors,
            "status": status,
            "created_at": days_ago(created_offset),
            "closed_at": days_ago(closed_offset) if closed_offset else None,
            "items": items
        })

    return audits

# ==============================================================================
# Helper to build 35 No-Dues clearance records
# ==============================================================================
def generate_nodues():
    students_data = [
        ("student_seed_0", "Ananya Rao", "CSE21A004", "In progress", "Library overdue book return pending"),
        ("student_seed_1", "Vikram Shah", "ME22B018", "Cleared", "All semester dues and lab clearance stamped"),
        ("student_seed_2", "Sara Thomas", "CE21C011", "In progress", "Surveying lab staff awaiting level instrument check"),
        ("student_demo_1", "Neha Gupta", "CSE21A012", "In progress", "Hostel key surrender pending"),
        ("student_demo_2", "Karan Patel", "ME22B033", "Cleared", "Clearance completed for campus placement"),
        ("student_nd_006", "Divya Krishnan", "BT23D005", "In progress", "Biotech cleanroom locker key unreturned"),
        ("student_nd_007", "Aditya Mishra", "ME23B045", "Pending", "Sports equipment hold (cricket bat missing)"),
        ("student_nd_008", "Pooja Hegde", "EE22A019", "Pending", "Electrical circuits breadboard kit missing"),
        ("student_nd_009", "Rohit Verma", "AR21A007", "Cleared", "All architecture studios cleared"),
        ("student_nd_010", "Siddharth Sen", "CSE21A028", "Cleared", "Degree graduation clearance issued"),
        ("student_nd_011", "Meenakshi Sundaram", "EC22B014", "Cleared", "All departmental dues verified nil"),
        ("student_nd_012", "Rishabh Jain", "ME21A044", "Cleared", "Machine shop locker verified clean"),
        ("student_nd_013", "Tanvi Deshpande", "CE22C009", "Cleared", "Concrete tech lab books returned"),
        ("student_nd_014", "Naveen Chawla", "BT21B003", "Cleared", "Biochemistry lab breakage fee cleared"),
        ("student_nd_015", "Shreya Ghoshal", "AR22A015", "Cleared", "Drafting tools kit handed over"),
        ("student_nd_016", "Harshavardhan Rao", "EE21A031", "Cleared", "Power lab project components surrendered"),
        ("student_nd_017", "Gaurav Malhotra", "CSE22B051", "In progress", "Library fines ₹120 unpaid"),
        ("student_nd_018", "Aishwarya Nair", "EC21A022", "In progress", "Hostel laundry dues pending verification"),
        ("student_nd_019", "Pranav Kulkarni", "ME23B012", "In progress", "Workshop apron & safety goggles missing"),
        ("student_nd_020", "Deepa Nambiar", "CE21C037", "In progress", "Hydraulics manual overdue"),
        ("student_nd_021", "Manish Tiwari", "BT22B019", "In progress", "Autoclave breakage receipt pending"),
        ("student_nd_022", "Sneha Bansal", "AR23A004", "In progress", "Model making workshop bay inspection pending"),
        ("student_nd_023", "Akash Shinde", "EE23B008", "In progress", "Transformer demo kit check pending"),
        ("student_nd_024", "Ritu Bharadwaj", "CSE21A066", "Cleared", "Clearance signed off by HOD"),
        ("student_nd_025", "Kunal Goswami", "ME22B049", "Cleared", "Foundry project clearance complete"),
        ("student_nd_026", "Varun Teja", "CE22C021", "Cleared", "Highway materials lab clearance complete"),
        ("student_nd_027", "Pallavi Joshi", "BT21B018", "Cleared", "Fermenter lab clearance signed"),
        ("student_nd_028", "Abhishek Saxena", "AR21A029", "Cleared", "Thesis drawings archived successfully"),
        ("student_nd_029", "Nandita Das", "EE22A044", "Cleared", "High voltage lab kit cleared"),
        ("student_nd_030", "Yash Chopra", "CSE23A011", "Pending", "Sports gym locker padlock unreturned"),
        ("student_nd_031", "Bhavna Swaminathan", "EC23B029", "Pending", "Digital electronics lab trainer kit held"),
        ("student_nd_032", "Tarun Reddy", "ME21A017", "Cleared", "Final year no-dues certificate ready"),
        ("student_nd_033", "Isha Mukherjee", "CE23C002", "Cleared", "No dues recorded across all cells"),
        ("student_nd_034", "Farhan Akhtar", "BT23D012", "Cleared", "Clearance verified for transcript dispatch"),
        ("student_nd_035", "Zoya Merchant", "AR22A033", "Cleared", "Design wing lockers cleared"),
    ]

    nodues = []
    departments_list = ["Library", "Hostel", "Sports", "Laboratory", "Accounts"]

    for sid, name, roll, overall, note in students_data:
        dept_statuses = []
        for d in departments_list:
            if overall == "Cleared":
                st = "Cleared"
                n = "Clearance verified"
            elif overall == "In progress":
                # 1 department has pending
                if (d == "Library" and "Library" in note) or (d == "Hostel" and "Hostel" in note) or (d == "Laboratory" and ("lab" in note.lower() or "workshop" in note.lower())):
                    st = "Pending"
                    n = note
                else:
                    st = "Cleared"
                    n = "Clear"
            else: # Pending
                if d in ["Sports", "Laboratory", "Library"]:
                    st = "Pending"
                    n = note
                else:
                    st = "Cleared"
                    n = "Clear"
                    
            dept_statuses.append({"department": d, "status": st, "note": n})

        nodues.append({
            "student_id": sid,
            "student_name": name,
            "roll_number": roll,
            "overall_status": overall,
            "department_statuses": dept_statuses,
            "updated_at": now_iso()
        })

    return nodues

# ==============================================================================
# Helper to build 300 Activity Logs (Audit Trail)
# ==============================================================================
def generate_activities(assets, maintenance, bookings, audits, nodues):
    events = []
    actors = [
        ("user_demo_admin", "Rohan Kapoor (Admin)"),
        ("user_demo_assetflow", "Maya Iyer (Asset Manager)"),
        ("user_demo_priya", "Dr. Priya Ramesh (HOD)"),
        ("user_demo_arjun", "Arjun Menon (Employee)"),
        ("user_mgr_kavita", "Kavita Deshmukh (Asset Manager)"),
        ("user_hod_rajesh", "Dr. Rajesh Sharma (HOD)"),
        ("user_emp_manish", "Manish Kulkarni (Technician)"),
        ("user_emp_tarun", "Tarun Bhatia (Network Admin)"),
        ("system", "AssetFlow Automated Monitor"),
    ]

    # Alerts (maintenance & audits) ~90 items
    for i in range(90):
        uid, uname = actors[i % len(actors)]
        m = maintenance[i % len(maintenance)]
        actions = ["maintenance request raised", "maintenance status changed", "maintenance photo attached", "priority escalated to High", "work order assigned to technician", "maintenance cycle closed"]
        action = actions[i % len(actions)]
        events.append({
            "event_id": f"evt_alert_{i+1:03d}",
            "actor_id": uid,
            "actor": uname,
            "action": action,
            "entity_type": "maintenance" if i % 3 != 0 else "audit",
            "entity_id": m["request_id"] if i % 3 != 0 else audits[i % len(audits)]["audit_id"],
            "before": None,
            "after": None,
            "metadata": {"priority": m.get("priority", "Medium")},
            "timestamp": days_ago(i // 3, hours=(i*5)%24, minutes=(i*11)%60)
        })

    # Approvals (user, department, category, report) ~70 items
    for i in range(70):
        uid, uname = actors[i % len(actors)]
        actions = ["role approved", "role changed", "user account activated", "department created", "category created", "report template created", "delegation scheduled", "accreditation export verified"]
        action = actions[i % len(actions)]
        entity_types = ["user", "department", "category", "report"]
        etype = entity_types[i % len(entity_types)]
        events.append({
            "event_id": f"evt_appr_{i+1:03d}",
            "actor_id": uid,
            "actor": uname,
            "action": action,
            "entity_type": etype,
            "entity_id": f"rec_{i+1:03d}",
            "before": None,
            "after": None,
            "metadata": {"approved": True},
            "timestamp": days_ago(i // 2, hours=(i*7)%24, minutes=(i*13)%60)
        })

    # Bookings ~60 items
    for i in range(60):
        uid, uname = actors[i % len(actors)]
        b = bookings[i % len(bookings)]
        actions = ["booking created", "booking confirmed", "booking reminder sent", "booking slot released", "booking cancelled"]
        action = actions[i % len(actions)]
        events.append({
            "event_id": f"evt_book_{i+1:03d}",
            "actor_id": uid,
            "actor": uname,
            "action": action,
            "entity_type": "booking",
            "entity_id": b["booking_id"],
            "before": None,
            "after": None,
            "metadata": {"resource": b.get("resource_name", "")},
            "timestamp": days_ago(i // 2, hours=(i*3)%24, minutes=(i*17)%60)
        })

    # Other (assets, nodues, branding) ~80 items
    for i in range(80):
        uid, uname = actors[i % len(actors)]
        a = assets[i % len(assets)]
        actions = ["asset registered", "asset checked out", "asset checked in", "asset location updated", "asset barcode scanned", "no-dues clearance stamped", "asset condition verified", "branding updated"]
        action = actions[i % len(actions)]
        events.append({
            "event_id": f"evt_other_{i+1:03d}",
            "actor_id": uid,
            "actor": uname,
            "action": action,
            "entity_type": "asset" if i % 4 != 0 else "nodues",
            "entity_id": a["asset_id"] if i % 4 != 0 else nodues[i % len(nodues)]["student_id"],
            "before": None,
            "after": None,
            "metadata": {"tag": a.get("tag", "")},
            "timestamp": days_ago(i // 3, hours=(i*4)%24, minutes=(i*9)%60)
        })

    # Sort all by timestamp descending
    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events

# ==============================================================================
# 8 Report Templates
# ==============================================================================
REPORT_TEMPLATES = [
    {
        "template_id": "tmpl_cs_lab_equipment",
        "name": "CS Department Lab Equipment Status",
        "description": "All lab machinery and computing equipment in Computer Science with allocation status and holder info",
        "data_source": "assets",
        "columns": ["tag", "name", "category", "location", "status", "holder", "serial", "purchase_cost"],
        "filters": {"department": "Computer Science", "category": "Lab Equipment"},
        "sort_by": "name",
        "sort_order": "asc",
        "access_roles": ["Admin", "Asset Manager", "HOD"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(60),
        "updated_at": days_ago(5),
        "is_active": True
    },
    {
        "template_id": "tmpl_allocated_assets",
        "name": "Campus-Wide Active Asset Allocations",
        "description": "All allocated equipment across all campus departments with responsible holder names and return dates",
        "data_source": "assets",
        "columns": ["tag", "name", "department", "location", "category", "holder", "serial"],
        "filters": {"status": "Allocated"},
        "sort_by": "department",
        "sort_order": "asc",
        "access_roles": ["Admin", "Asset Manager", "HOD", "Employee"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(50),
        "updated_at": days_ago(3),
        "is_active": True
    },
    {
        "template_id": "tmpl_open_maintenance",
        "name": "Open Maintenance Work Orders",
        "description": "Pending and in-progress repair tickets needing immediate technician intervention across campus",
        "data_source": "maintenance",
        "columns": ["request_id", "asset_id", "priority", "status", "description", "raised_by", "created_at"],
        "filters": {"status": "In progress"},
        "sort_by": "created_at",
        "sort_order": "desc",
        "access_roles": ["Admin", "Asset Manager", "HOD"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(40),
        "updated_at": days_ago(2),
        "is_active": True
    },
    {
        "template_id": "tmpl_high_value_assets",
        "name": "High-Value Capital Equipment (>₹50,000)",
        "description": "High value scientific, machinery, and IT infrastructure subject to annual physical board audit",
        "data_source": "assets",
        "columns": ["tag", "name", "category", "department", "purchase_cost", "supplier", "warranty_end"],
        "filters": {},
        "sort_by": "purchase_cost",
        "sort_order": "desc",
        "access_roles": ["Admin", "Asset Manager"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(35),
        "updated_at": days_ago(1),
        "is_active": True
    },
    {
        "template_id": "tmpl_bookable_fleet",
        "name": "Campus Facilities & Vehicle Fleet",
        "description": "All bookable seminar halls, buses, and loaner electronics available for reservation",
        "data_source": "assets",
        "columns": ["tag", "name", "category", "location", "department", "status"],
        "filters": {"bookable": True},
        "sort_by": "category",
        "sort_order": "asc",
        "access_roles": ["Admin", "Asset Manager", "HOD", "Employee", "Student"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(30),
        "updated_at": days_ago(1),
        "is_active": True
    },
    {
        "template_id": "tmpl_workshop_machinery",
        "name": "Mechanical Workshop Heavy Machinery",
        "description": "Heavy industrial lathes, mills, press brakes and welding bays in Mechanical Engineering",
        "data_source": "assets",
        "columns": ["tag", "name", "location", "status", "serial", "supplier", "amc_provider"],
        "filters": {"category": "Workshop Machinery"},
        "sort_by": "name",
        "sort_order": "asc",
        "access_roles": ["Admin", "Asset Manager", "HOD"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(25),
        "updated_at": days_ago(2),
        "is_active": True
    },
    {
        "template_id": "tmpl_it_infrastructure",
        "name": "IT & Network Hardware Roster",
        "description": "Core switches, firewalls, and server racks managed by Campus IT Services",
        "data_source": "assets",
        "columns": ["tag", "name", "location", "status", "serial", "warranty_end", "supplier"],
        "filters": {"category": "Network Infrastructure"},
        "sort_by": "location",
        "sort_order": "asc",
        "access_roles": ["Admin", "Asset Manager"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(20),
        "updated_at": days_ago(1),
        "is_active": True
    },
    {
        "template_id": "tmpl_maintenance_all",
        "name": "Complete Work Order Resolution History",
        "description": "Closed and in-progress maintenance tickets for accreditation compliance audit",
        "data_source": "maintenance",
        "columns": ["request_id", "asset_id", "priority", "status", "raised_by", "created_at", "resolved_at"],
        "filters": {},
        "sort_by": "created_at",
        "sort_order": "desc",
        "access_roles": ["Admin", "Asset Manager", "HOD"],
        "created_by": "user_demo_admin",
        "created_by_name": "Rohan Kapoor",
        "created_at": days_ago(15),
        "updated_at": days_ago(1),
        "is_active": True
    }
]

# ==============================================================================
# 6 Delegations
# ==============================================================================
DELEGATIONS = [
    {
        "delegation_id": "deleg_001",
        "admin_id": "user_demo_admin",
        "admin_name": "Rohan Kapoor",
        "deputy_id": "user_demo_assetflow",
        "deputy_name": "Maya Iyer",
        "deputy_original_role": "Asset Manager",
        "start_at": days_ago(2),
        "end_at": days_ahead(5),
        "note": "Authorized admin coverage during annual accreditation review conference",
        "status": "Scheduled",
        "created_at": days_ago(5)
    },
    {
        "delegation_id": "deleg_002",
        "admin_id": "user_demo_admin",
        "admin_name": "Rohan Kapoor",
        "deputy_id": "user_demo_priya",
        "deputy_name": "Dr. Priya Ramesh",
        "deputy_original_role": "HOD",
        "start_at": days_ahead(10),
        "end_at": days_ahead(17),
        "note": "Coverage during university senate meeting travel",
        "status": "Scheduled",
        "created_at": days_ago(3)
    },
    {
        "delegation_id": "deleg_003",
        "admin_id": "user_admin_neha",
        "admin_name": "Dr. Neha Agarwal",
        "deputy_id": "user_mgr_suresh",
        "deputy_name": "Suresh Nair",
        "deputy_original_role": "Asset Manager",
        "start_at": days_ahead(20),
        "end_at": days_ahead(25),
        "note": "Institutional audit procurement signoff coverage",
        "status": "Scheduled",
        "created_at": days_ago(2)
    },
    {
        "delegation_id": "deleg_004",
        "admin_id": "user_demo_admin",
        "admin_name": "Rohan Kapoor",
        "deputy_id": "user_demo_arjun",
        "deputy_name": "Arjun Menon",
        "deputy_original_role": "Employee",
        "start_at": days_ago(25),
        "end_at": days_ago(18),
        "note": "Workshop safety sign-off coverage",
        "status": "Expired",
        "created_at": days_ago(30)
    },
    {
        "delegation_id": "deleg_005",
        "admin_id": "user_demo_admin",
        "admin_name": "Rohan Kapoor",
        "deputy_id": "user_mgr_kavita",
        "deputy_name": "Kavita Deshmukh",
        "deputy_original_role": "Asset Manager",
        "start_at": days_ago(10),
        "end_at": days_ago(5),
        "note": "Replaced by direct admin presence",
        "status": "Revoked",
        "revoked_at": days_ago(8),
        "created_at": days_ago(12)
    },
    {
        "delegation_id": "deleg_006",
        "admin_id": "user_admin_neha",
        "admin_name": "Dr. Neha Agarwal",
        "deputy_id": "user_emp_manish",
        "deputy_name": "Manish Kulkarni",
        "deputy_original_role": "Employee",
        "start_at": days_ahead(30),
        "end_at": days_ahead(35),
        "note": "Technical stores dispatch deputy",
        "status": "Scheduled",
        "created_at": days_ago(1)
    },
]

# ==============================================================================
# Branding
# ==============================================================================
BRANDING = {
    "_id": "singleton",
    "institution_name": "AssetFlow Campus Institute of Technology",
    "tagline": "Every asset. Accountable. NAAC & NBA Compliant.",
    "accreditation_body": "NAAC A++ / NBA Accredited",
    "footer": "This report is a machine-generated snapshot for NAAC/NBA accreditation review. Figures are drawn from AssetFlow Campus activity logs and can be re-verified from the workspace.",
    "accent_color": "#171717",
    "logo_url": ""
}

# ==============================================================================
# MAIN SEED RUNNER
# ==============================================================================
async def run_seed(drop_existing=True):
    print("=" * 60)
    print(f"Connecting to MongoDB: {DB_NAME}...")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    if drop_existing:
        print("Cleaning previous seed datasets for fresh population...")
        await db.departments.delete_many({})
        await db.categories.delete_many({})
        await db.users.delete_many({})
        await db.assets.delete_many({})
        await db.maintenance.delete_many({})
        await db.bookings.delete_many({})
        await db.audits.delete_many({})
        await db.nodues.delete_many({})
        await db.activity.delete_many({})
        await db.report_templates.delete_many({})
        await db.delegations.delete_many({})
        await db.branding.delete_many({})

    # 1. Departments
    print(f"Seeding {len(DEPARTMENTS)} departments...")
    for d in DEPARTMENTS:
        d["created_at"] = now_iso()
    await db.departments.insert_many(DEPARTMENTS)

    # 2. Categories
    print(f"Seeding {len(CATEGORIES)} categories...")
    for c in CATEGORIES:
        c["created_at"] = now_iso()
    await db.categories.insert_many(CATEGORIES)

    # 3. Users
    print(f"Seeding {len(USERS)} users & demo accounts...")
    for u in USERS:
        u["created_at"] = now_iso()
        u["picture"] = ""
    await db.users.insert_many(USERS)

    # 4. Assets
    assets = generate_assets()
    print(f"Seeding {len(assets)} realistic assets spanning all conditions & categories...")
    await db.assets.insert_many(assets)

    # 5. Maintenance
    maintenance = generate_maintenance(assets)
    print(f"Seeding {len(maintenance)} maintenance work orders...")
    await db.maintenance.insert_many(maintenance)

    # 6. Bookings
    bookings = generate_bookings(assets)
    print(f"Seeding {len(bookings)} resource reservations & calendar agenda...")
    await db.bookings.insert_many(bookings)

    # 7. Audits
    audits = generate_audits(assets)
    print(f"Seeding {len(audits)} audit cycles with verified/missing/damaged items...")
    await db.audits.insert_many(audits)

    # 8. No-Dues
    nodues = generate_nodues()
    print(f"Seeding {len(nodues)} student no-dues clearance records...")
    await db.nodues.insert_many(nodues)

    # 9. Activities
    activities = generate_activities(assets, maintenance, bookings, audits, nodues)
    print(f"Seeding {len(activities)} activity logs (audit trail)...")
    await db.activity.insert_many(activities)

    # 10. Report templates
    print(f"Seeding {len(REPORT_TEMPLATES)} custom report templates...")
    await db.report_templates.insert_many(REPORT_TEMPLATES)

    # 11. Delegations
    print(f"Seeding {len(DELEGATIONS)} administrative delegation slots...")
    await db.delegations.insert_many(DELEGATIONS)

    # 12. Branding
    print("Setting institutional accreditation branding...")
    await db.branding.update_one({"_id": "singleton"}, {"$set": BRANDING}, upsert=True)

    print("=" * 60)
    print("SUCCESS: Comprehensive seed data has been fully populated!")
    print(f"  - Assets:           {await db.assets.count_documents({})}")
    print(f"  - Maintenance:      {await db.maintenance.count_documents({})}")
    print(f"  - Bookings:         {await db.bookings.count_documents({})}")
    print(f"  - Audits:           {await db.audits.count_documents({})}")
    print(f"  - No-Dues Students: {await db.nodues.count_documents({})}")
    print(f"  - Activity Logs:    {await db.activity.count_documents({})}")
    print(f"  - Users:            {await db.users.count_documents({})}")
    print(f"  - Departments:      {await db.departments.count_documents({})}")
    print(f"  - Categories:       {await db.categories.count_documents({})}")
    print(f"  - Templates:        {await db.report_templates.count_documents({})}")
    print(f"  - Delegations:      {await db.delegations.count_documents({})}")
    print("=" * 60)
    client.close()

if __name__ == "__main__":
    drop = "--keep" not in sys.argv
    asyncio.run(run_seed(drop_existing=drop))
