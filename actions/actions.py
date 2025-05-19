import requests
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from rasa_sdk.forms import FormValidationAction
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from typing import Any, Dict, List, Text, Optional

load_dotenv()
together_api_key = os.getenv("TOGETHER_API_KEY")

class ActionGPTAnswer(Action):
    def name(self):
        return "action_gpt_answer"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        user_input = tracker.latest_message.get("text")

        if not any(k in user_input.lower() for k in
                   ["gigi", "klinik", "dokter", "perawatan", "karang", "tambal",
                    "scaling", "cabut", "sakit", "berdarah", "gusi", "nyeri", "mulut"]):
            dispatcher.utter_message(text="Maaf, saya hanya menjawab pertanyaan tentang layanan dan perawatan gigi ya 🙂")
            return []

        try:
            response = requests.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {together_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta-llama/Llama-3-8b-chat-hf",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Kamu adalah chatbot untuk klinik gigi. Jawablah setiap pertanyaan dengan gaya santai tapi tetap serius dan profesional. "
                                "Jawaban harus langsung to the point, tidak mengulang pertanyaan, tidak membuka dengan basa-basi atau ketawa. "
                                "Gunakan Bahasa Indonesia dan boleh pakai emoji agar tidak terlalu kaku. "
                                "Jangan menjawab pertanyaan di luar topik gigi, dokter gigi, perawatan mulut, dan layanan klinik gigi."
                            )
                        },
                        {
                            "role": "user",
                            "content": user_input
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 200
                },
                timeout=60
            )

            result = response.json()
            answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        except Exception as e:
            answer = f"❌ Error saat menghubungi model: {str(e)}"

        dispatcher.utter_message(text=answer)
        return []

class ActionCekJadwalDokter(Action):
    def name(self):
        return "action_cek_jadwal_dokter"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        nama_dokter = tracker.get_slot("nama_dokter")

        if not nama_dokter:
            dispatcher.utter_message(text="Siapa nama dokternya ya?")
            return []

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_path = os.path.join(os.path.dirname(__file__), "sharp-kayak-459602-i8-bf30544ffcf8.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)

        sheet = client.open("JadwalDokter").sheet1
        data = sheet.get_all_records()

        jadwal_dokter = None
        for row in data:
            if row["Nama Dokter"].lower() == nama_dokter.lower():
                jadwal_dokter = row["Jadwal"]
                break

        if jadwal_dokter:
            dispatcher.utter_message(text=f"Jadwal {nama_dokter}: {jadwal_dokter}")
        else:
            dispatcher.utter_message(text="Wah, aku belum nemu jadwalnya. Coba pastikan nama dokternya benar ya!")

        return []

class ActionSemuaJadwalDokter(Action):
    def name(self):
        return "action_semua_jadwal_dokter"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            json_path = os.path.join(os.path.dirname(__file__), "sharp-kayak-459602-i8-bf30544ffcf8.json")
            creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
            client = gspread.authorize(creds)

            sheet = client.open("JadwalDokter").sheet1
            records = sheet.get_all_records()

            response = "Berikut jadwal dokter:\n"
            for row in records:
                response += f"- {row['Nama Dokter']}: {row['Jadwal']}\n"

            dispatcher.utter_message(text=response)

        except Exception as e:
            dispatcher.utter_message(text=f"Gagal ambil data dari Google Sheet: {str(e)}")

        return []

class ValidateFormJanjiTemu(FormValidationAction):
    def name(self) -> Text:
        return "validate_form_janji_temu"

    def validate_nama(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker, domain: DomainDict) -> Dict[Text, Any]:
        return {"nama": slot_value.strip()}

    def validate_dokter(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker, domain: DomainDict) -> Dict[Text, Any]:
        match = re.search(r"dr(?:\.| )?([\w\s]+)", slot_value, re.IGNORECASE)
        if match:
            return {"dokter": match.group(1).strip()}
        return {"dokter": slot_value.strip()}

    def validate_tanggal(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker, domain: DomainDict) -> Dict[Text, Any]:
        match = re.search(r"(senin|selasa|rabu|kamis|jumat|sabtu|minggu|\d{1,2}/\d{1,2}/\d{4})", slot_value, re.IGNORECASE)
        if match:
            return {"tanggal": match.group(1).strip()}
        return {"tanggal": slot_value.strip()}

    def validate_jam(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker, domain: DomainDict) -> Dict[Text, Any]:
        match = re.search(r"(\d{1,2}:\d{2})", slot_value)
        if match:
            return {"jam": match.group(1).strip()}
        return {"jam": slot_value.strip()}

    def validate_kontak(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker, domain: DomainDict) -> Dict[Text, Any]:
        match = re.search(r"(\+?\d{10,15})", slot_value)
        if match:
            return {"kontak": match.group(1).strip()}
        return {"kontak": slot_value.strip()}

    def validate_jenis_pengobatan(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker, domain: DomainDict) -> Dict[Text, Any]:
        match = re.search(r"(scaling|tambal|cabut|perawatan[\w\s]*)", slot_value, re.IGNORECASE)
        if match:
            return {"jenis_pengobatan": match.group(1).strip()}
        return {"jenis_pengobatan": slot_value.strip()}

class ActionSimpanJanjiTemu(Action):
    def name(self):
        return "action_simpan_janji_temu"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        try:
            nama = (tracker.get_slot("nama") or "").strip()
            dokter = (tracker.get_slot("dokter") or "").strip()
            tanggal = (tracker.get_slot("tanggal") or "").strip()
            jam = (tracker.get_slot("jam") or "").strip()
            kontak = (tracker.get_slot("kontak") or "").strip()
            jenis_pengobatan = (tracker.get_slot("jenis_pengobatan") or "").strip()

            if not all([nama, dokter, tanggal, jam, kontak, jenis_pengobatan]):
                dispatcher.utter_message(text="❌ Data belum lengkap. Mohon lengkapi semua informasi.")
                return []

            dispatcher.utter_message(
                text=f"✅ Janji temu berhasil disimpan!\n"
                     f"Nama: {nama}\nDokter: {dokter}\nTanggal: {tanggal}\nJam: {jam}\nKontak: {kontak}\nPerawatan: {jenis_pengobatan}"
            )
        except Exception as e:
            dispatcher.utter_message(text=f"❌ Gagal menyimpan janji temu: {str(e)}")

        return []

def ambil_nama_dokter_dari_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_path = os.path.join(os.path.dirname(__file__), "sharp-kayak-459602-i8-bf30544ffcf8.json")
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open("JadwalDokter").sheet
