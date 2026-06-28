CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE patients (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(50) NOT NULL,
    relation VARCHAR(30) NOT NULL,
    age INTEGER NOT NULL,
    gender VARCHAR(10) NOT NULL,
    id_card_no VARCHAR(30) NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    alias VARCHAR(200) NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE doctors (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    department_id INTEGER NOT NULL,
    title VARCHAR(50) NOT NULL,
    specialty VARCHAR(200) NOT NULL,
    is_expert BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(department_id) REFERENCES departments(id)
);

CREATE TABLE doctor_schedules (
    id INTEGER PRIMARY KEY,
    doctor_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    work_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_type VARCHAR(20) NOT NULL,
    total_count INTEGER NOT NULL,
    remain_count INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    FOREIGN KEY(doctor_id) REFERENCES doctors(id),
    FOREIGN KEY(department_id) REFERENCES departments(id)
);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    schedule_id INTEGER NOT NULL,
    appointment_time DATETIME NOT NULL,
    slot_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL,
    cancelled_at DATETIME NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(patient_id) REFERENCES patients(id),
    FOREIGN KEY(doctor_id) REFERENCES doctors(id),
    FOREIGN KEY(department_id) REFERENCES departments(id),
    FOREIGN KEY(schedule_id) REFERENCES doctor_schedules(id)
);

CREATE TABLE agent_task_states (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    slots_json TEXT NOT NULL,
    state VARCHAR(20) NOT NULL,
    result TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE agent_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    tool_input TEXT NOT NULL,
    tool_output TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    error_message TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
