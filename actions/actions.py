import requests
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher


load_dotenv()
together_api_key = os.getenv("TOGETHER_API_KEY")

class ActionGPTAnswer(Action):
    def name(self):
        return "action_gpt_answer"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        user_input = tracker.latest_message.get("text")

        try:
            response = requests.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {together_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                    "messages": [
                        {
                            "role": "system",
                            "content":
                                "Kamu adalah chatbot untuk klinik gigi yang bernama gigita dental care. Jawablah pertanyaan berikut dengan gaya santai, boleh pakai emot seperti '😊' '😁' '🦷', atau lainnya biar tidak terlalu kaku, pakai Bahasa Indonesia.\n"
                                "Jawaban harus langsung ke poinnya, boleh pakai emot, dan hindari mengulang pertanyaan user. "
                                "Jangan pakai label seperti 'Jawaban:', 'Solution:', atau tanda ```.\n"
                                "Kalau topiknya di luar kesehatan atau layanan gigi, cukup bilang tidak bisa bantu."
                                "Kalau pertanyaan user tidak mengandung kata kunci seperti 'gigi', 'dokter', 'klinik', 'perawatan', 'gusi', 'bengkak', 'sakit', 'tambal', 'scaling', atau topik lain terkait kesehatan gigi — JANGAN JAWAB, cukup katakan tidak bisa membantu karena topiknya di luar layanan gigi"
                           },
                        {
                            "role": "user",
                            "content": user_input
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=60
            )


            result = response.json()
            answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            # Deteksi kata kunci keluhan
            keluhan_keywords = ["sakit", "bengkak", "berdarah", "ngilu", "copot", "retak", "nyeri", "perih"]
            if any(k in user_input.lower() for k in keluhan_keywords):
                cta = "\n\nKalau kamu merasa tidak nyaman dengan kondisi gigi atau gusi, kami sarankan untuk booking janji temu dengan dokter melalui whatsapp kami di 085179966117 ya 😊"
                answer += cta

            # Kalau pertanyaan di luar topik gigi, kasih respon default
            if not any(k in user_input.lower() for k in
                       ["gigi", "klinik", "dokter", "perawatan", "karang", "tambal", "scaling", "cabut", "gusi"]):
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

            sheet = client.open("JadwalDokter").sheet1  # Ganti sesuai nama Sheet

            records = sheet.get_all_records()

            response = "Berikut jadwal dokter:\n"
            for row in records:
                response += f"- {row['Nama Dokter']}: {row['Jadwal']}\n"

            dispatcher.utter_message(text=response)

        except Exception as e:
            dispatcher.utter_message(text=f"Gagal ambil data dari Google Sheet: {str(e)}")

        return []
