"""
UserInfoWidget - shows logged-in user information
"""
from typing import Dict, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLabel


class UserInfoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.user_group = QGroupBox("User Information")
        user_layout = QFormLayout()

        self.name_label = QLabel("-")
        self.rank_label = QLabel("-")
        self.flights_label = QLabel("-")
        self.flight_time_label = QLabel("-")
        self.current_airport_label = QLabel("-")

        user_layout.addRow("Name:", self.name_label)
        user_layout.addRow("Rank ID:", self.rank_label)
        user_layout.addRow("Total Flights:", self.flights_label)
        user_layout.addRow("Flight Time:", self.flight_time_label)
        user_layout.addRow("Current Airport:", self.current_airport_label)

        self.user_group.setLayout(user_layout)
        layout.addWidget(self.user_group)

        self.setLayout(layout)

    def update_user_info(self, user_data: Dict[str, Any]):
        self.name_label.setText(user_data.get('name', 'Unknown'))
        self.rank_label.setText(str(user_data.get('rank', {}).get('name', 'Unknown')))
        self.flights_label.setText(str(user_data.get('flights', 0)))

        # Convert flight time from minutes to hours:minutes
        flight_time_minutes = user_data.get('flight_time', 0)
        hours = flight_time_minutes // 60
        minutes = flight_time_minutes % 60
        self.flight_time_label.setText(f"{hours}h {minutes}m")

        self.current_airport_label.setText(user_data.get('curr_airport', 'Unknown'))
