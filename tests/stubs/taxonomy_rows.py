"""
Realistic NUCC taxonomy rows for testing RAG pipeline.
Based on actual NUCC Healthcare Provider Taxonomy CSV structure.
"""

# Sample taxonomy rows with code, classification, specialization, description
TAXONOMY_ROWS = [
    {
        "code": "207Q00000X",
        "classification": "Family Medicine",
        "specialization": "General Practice",
        "description": "Family Medicine is the medical specialty which provides continuing, comprehensive health care for the individual and family."
    },
    {
        "code": "207R00000X",
        "classification": "Internal Medicine",
        "specialization": None,
        "description": "Internal Medicine is the medical specialty dealing with the prevention, diagnosis, and treatment of adult diseases."
    },
    {
        "code": "207W00000X",
        "classification": "Ophthalmology",
        "specialization": None,
        "description": "Ophthalmology is a branch of medicine which deals with the anatomy, physiology and diseases of the eye."
    },
    {
        "code": "208D00000X",
        "classification": "General Practice",
        "specialization": None,
        "description": "The practitioner is a doctor of medicine or doctor of osteopathy who is not designated in any other category."
    },
    {
        "code": "208M00000X",
        "classification": "Maternal & Fetal Medicine",
        "specialization": None,
        "description": "An obstetrician/gynecologist who cares for patients with obstetric and gynecologic medical and surgical problems."
    },
    {
        "code": "207N00000X",
        "classification": "Dermatology",
        "specialization": None,
        "description": "Dermatology is the specialty of medicine that deals with the skin, nails, hair and their diseases."
    },
    {
        "code": "207P00000X",
        "classification": "Emergency Medicine",
        "specialization": None,
        "description": "Emergency Medicine focuses on the immediate decision making and action necessary to prevent death or any further disability."
    },
    {
        "code": "207T00000X",
        "classification": "Surgery",
        "specialization": None,
        "description": "Surgery is a branch of medicine that involves operative treatment of injuries, diseases, and deformities."
    },
    {
        "code": "207V00000X",
        "classification": "Obstetrics & Gynecology",
        "specialization": "Obstetrics",
        "description": "Obstetrics & Gynecology is the medical specialty that deals with the care of women's reproductive health."
    },
    {
        "code": "207W00000X",
        "classification": "Ophthalmology",
        "specialization": "Cornea and External Disease",
        "description": "A subspecialist that manages problems of the anterior and posterior segments of the eye."
    },
    {
        "code": "208600000X",
        "classification": "Pediatrics",
        "specialization": None,
        "description": "Pediatrics is the specialty of medicine that deals with the medical care of infants, children, and adolescents."
    },
    {
        "code": "2088X0000X",
        "classification": "Pediatric Gastroenterology",
        "specialization": None,
        "description": "A pediatrician who specializes in the diagnosis and treatment of diseases of the digestive systems of infants, children and adolescents."
    },
    {
        "code": "207RC0000X",
        "classification": "Internal Medicine",
        "specialization": "Cardiovascular Disease",
        "description": "An internist who specializes in diseases of the heart and blood vessels and manages complex cardiac conditions."
    },
    {
        "code": "207RE0000X",
        "classification": "Internal Medicine",
        "specialization": "Endocrinology",
        "description": "An internist who specializes in the diagnosis and treatment of disorders of the endocrine system."
    },
    {
        "code": "207RI0000X",
        "classification": "Internal Medicine",
        "specialization": "Interventional Cardiology",
        "description": "An internist who diagnoses and treats diseases of the coronary arteries and veins."
    }
]

# Simple CSV-like string for parsing tests
TAXONOMY_CSV = """code,classification,specialization,description
207Q00000X,Family Medicine,General Practice,"Family Medicine is the medical specialty which provides continuing, comprehensive health care for the individual and family."
207R00000X,Internal Medicine,,"Internal Medicine is the medical specialty dealing with the prevention, diagnosis, and treatment of adult diseases."
207W00000X,Ophthalmology,,"Ophthalmology is a branch of medicine which deals with the anatomy, physiology and diseases of the eye."
207N00000X,Dermatology,,"Dermatology is the specialty of medicine that deals with the skin, nails, hair and their diseases."
208600000X,Pediatrics,,"Pediatrics is the specialty of medicine that deals with the medical care of infants, children, and adolescents."
207RC0000X,Internal Medicine,Cardiovascular Disease,"An internist who specializes in diseases of the heart and blood vessels and manages complex cardiac conditions."
"""