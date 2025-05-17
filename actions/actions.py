import requests
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from rasa_sdk.forms import FormValidationAction
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher

load_dotenv()
together_api_key = os.getenv("TOGETHER_API_KEY")

class ActionGPTAnswer(Action):
    def name(self):
        return "action_gpt_answer"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        user_input = tracker.latest_message.get("text")

        prompt = (
            f"Kamu adalah chatbot untuk klinik gigi. Jawablah pertanyaan berikut dengan gaya santai tapi tetap serius dan kelihatan profesional, boleh pakai emot biar tidak terlalu kaku, pakai Bahasa Indonesia.\n"
            f"Jangan pernah membalas dalam bentuk kode, skrip, atau format Markdown.\n"
            f"Jawaban kamu harus langsung to the point hindari mengulang pertanyaan user.\n"
            f"Jangan menjawab topik di luar kesehatan atau layanan gigi.\n"
            f"Kalau pertanyaan user tidak mengandung kata kunci seperti 'gigi', 'dokter', 'klinik', 'perawatan', atau topik lain terkait kesehatan gigi — JANGAN JAWAB, cukup katakan tidak bisa membantu karena topiknya di luar layanan gigi.\n"
            f"Pertanyaan user: {user_input}\n"
            f"Jawaban kamu:"
        )

        try:
            response = requests.post(
                "https://api.together.xyz/v1/completions",
                headers={
                    "Authorization": f"Bearer {together_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta-llama/Llama-3-8b-chat-hf",
                    "prompt": prompt,
                    "max_tokens": 200,
                    "temperature": 0.7,
                    "stop": ["\n\n", "```"]
                },
                timeout=60
            )

            result = response.json()
            answer = result.get("choices", [{}])[0].get("text", "").strip()

            if not any(k in user_input.lower() for k in
                       ["gigi", "klinik", "dokter", "perawatan", "karang", "tambal", "scaling", "cabut"]):
                answer = "Maaf, saya hanya menjawab pertanyaan tentang layanan dan perawatan gigi ya 🙂"


        except Exception as e:
            answer = f"Ada error nih: {str(e)}"

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

        # Setup akses ke Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_path = os.path.join(os.path.dirname(__file__), "sharp-kayak-459602-i8-bf30544ffcf8.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)

        sheet = client.open("JadwalDokter").sheet1  # Nama file & tab pertama

        # Ambil semua data
        data = sheet.get_all_records()

        # Cari dokter
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
            # Setup credentials
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            json_path = os.path.join(os.path.dirname(__file__), "sharp-kayak-459602-i8-bf30544ffcf8.json")
            creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
            client = gspread.authorize(creds)

            # Open the Google Sheet by name
            sheet = client.open("JadwalDokter").sheet1  # Ganti sesuai nama Sheet

            # Ambil semua data
            records = sheet.get_all_records()

            response = "Berikut jadwal dokter:\n"
            for row in records:
                response += f"- {row['Nama Dokter']}: {row['Jadwal']}\n"

            dispatcher.utter_message(text=response)

        except Exception as e:
            dispatcher.utter_message(text=f"Gagal ambil data dari Google Sheet: {str(e)}")

        return []

class ActionSimpanJanjiTemu(Action):
    def name(self):
        return "action_simpan_janji_temu"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        try:
            text = tracker.latest_message.get("text", "").lower()

            nama = (tracker.get_slot("nama") or "").strip()
            dokter = (tracker.get_slot("dokter") or "").strip()
            tanggal = (tracker.get_slot("tanggal") or "").strip()
            jam = (tracker.get_slot("jam") or "").strip()
            kontak = (tracker.get_slot("kontak") or "").strip()
            jenis_pengobatan = (tracker.get_slot("jenis_pengobatan") or "").strip()

            # Coba ambil dari text jika slot kosong
            if not nama:
                match = re.search(r"nama(?: saya)? (?:adalah )?([\w\s]+)", text)
                if match:
                    nama = match.group(1).strip()

            if not dokter:
                match = re.search(r"dr(?:\.| )?([\w\s]+)", text)
                if match:
                    dokter = match.group(1).strip()

            if not tanggal:
                match = re.search(r"hari ([\w\s]+)", text)
                if match:
                    tanggal = match.group(1).strip()

            if not jam:
                match = re.search(r"jam ([\d\w\s.:]+)", text)
                if match:
                    jam = match.group(1).strip()

            if not kontak:
                match = re.search(r"(?:kontak|nomor|no hp)[\s:]*([\d+]+)", text)
                if match:
                    kontak = match.group(1).strip()

            if not jenis_pengobatan:
                match = re.search(r"(scaling|tambal|cabut|perawatan[\w\s]*)", text)
                if match:
                    jenis_pengobatan = match.group(1).strip()

            if not all([nama, dokter, tanggal, jam, kontak, jenis_pengobatan]):
                dispatcher.utter_message(text="❌ Data belum lengkap. Mohon lengkapi semua informasi.")
                return []

            # simpan ke Google Sheets
            # (lanjut seperti sebelumnya)

            # ...
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
    sheet = client.open("JadwalDokter").sheet1
    data = sheet.get_all_records()
    return [row["Nama Dokter"].strip().lower() for row in data]

class ValidateFormJanjiTemu(FormValidationAction):
    def name(self) -> str:
        return "validate_form_janji_temu"

    def validate_dokter(self, slot_value: str, dispatcher, tracker, domain):
        daftar_dokter = ambil_nama_dokter_dari_sheet()
        if slot_value.lower() in daftar_dokter:
            return {"dokter": slot_value}
        else:
            dispatcher.utter_message(text=f"❌ Dokter {slot_value} tidak ditemukan dalam daftar jadwal.")
            return {"dokter": None}
