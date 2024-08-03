import tkinter as tk
from tkinter import scrolledtext, simpledialog, Menu, messagebox
from tkinter.ttk import Treeview
from openai import OpenAI
from dotenv import load_dotenv
import os
import time
import json
import pyperclip

# Load the API key from the .env file
load_dotenv()
openai_api_key = os.getenv('api_key')

# Initialize OpenAI client
client = OpenAI(api_key=openai_api_key)

# Directory to store conversations
CONVERSATION_DIR = "conversations"
os.makedirs(CONVERSATION_DIR, exist_ok=True)

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ChatGPT by JL")

        # Setup menu
        self.setup_menu()

        # Creating frames for better layout
        self.chat_frame = tk.Frame(root)
        self.chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.sidebar_frame = tk.Frame(root)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.new_conv_button = tk.Button(self.sidebar_frame, text="New Conversation", command=self.new_conversation)
        self.new_conv_button.pack(pady=5, side=tk.TOP)

        self.sidebar = Treeview(self.sidebar_frame)
        self.sidebar.heading("#0", text="Conversations")
        self.sidebar.pack(fill=tk.Y, expand=True)
        self.sidebar.bind("<ButtonRelease-1>", self.load_conversation)
        self.sidebar.bind("<Button-3>", self.show_context_menu)
        self.sidebar.bind("<Button-2>", self.show_context_menu)

        # Setting font size
        font_settings = ("Helvetica", 14)

        self.chat_display = scrolledtext.ScrolledText(self.chat_frame, wrap=tk.WORD, width=80, height=40, font=font_settings)
        self.chat_display.pack(padx=5, pady=10, fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED)

        self.user_input = tk.Entry(self.chat_frame, width=80, font=font_settings)
        self.user_input.pack(padx=10, pady=10, fill=tk.X)
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(self.chat_frame, text="Send", command=self.send_message)
        self.send_button.pack(pady=5)

        self.load_conversations()
        self.chat_history = []
        self.current_conversation_title = None

        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Rename", command=self.rename_conversation)
        self.context_menu.add_command(label="Delete", command=self.delete_conversation)

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_command(label="Set API Key", command=self.set_api_key)
    
    def set_api_key(self):
        new_key = simpledialog.askstring("Set API Key", "Enter your OpenAI API Key:")
        if new_key:
            with open('.env', 'w') as f:
                f.write(f"api_key={new_key}\n")
            messagebox.showinfo("Success", "API Key has been updated!")
            load_dotenv()  # Reload the .env file to update the API key
            self.openai_api_key = os.getenv('api_key')
            client.api_key = self.openai_api_key

    def new_conversation(self):
        self.chat_history = [{"role": "system", "content": "You are a helpful assistant."}]
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.user_input.delete(0, tk.END)
        self.current_conversation_title = None

    def delete_conversation(self):
        selected_item = self.sidebar.selection()
        if selected_item:
            title = self.sidebar.item(selected_item, "text")
            confirm = messagebox.askyesno("Delete Conversation", f"Are you sure you want to delete the conversation '{title}'?")
            if confirm:
                file_path = os.path.join(CONVERSATION_DIR, f"{title}.json")
                if os.path.exists(file_path):
                    os.remove(file_path)
                self.sidebar.delete(selected_item)
                self.chat_display.config(state=tk.NORMAL)
                self.chat_display.delete(1.0, tk.END)
                self.chat_display.config(state=tk.DISABLED)
                self.user_input.delete(0, tk.END)
                self.current_conversation_title = None

    def load_conversation(self, event):
        selected_item = self.sidebar.selection()
        if selected_item:
            title = self.sidebar.item(selected_item, "text")
            file_path = os.path.join(CONVERSATION_DIR, f"{title}.json")
            with open(file_path, 'r') as file:
                self.chat_history = json.load(file)
                self.display_full_conversation()
            self.current_conversation_title = title

    def display_full_conversation(self):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        for message in self.chat_history:
            if message['role'] == 'user':
                self.insert_user_message(message['content'])
            else:
                self.insert_assistant_message(message['content'])
        self.chat_display.config(state=tk.DISABLED)

    def send_message(self, event=None):
        user_message = self.user_input.get()
        if not user_message:
            return

        self.insert_user_message(user_message)
        self.chat_history.append({"role": "user", "content": user_message})
        self.user_input.delete(0, tk.END)

        response = self.get_openai_response()
        self.insert_assistant_message(response)
        self.chat_history.append({"role": "assistant", "content": response})
        self.save_current_conversation()

    def insert_user_message(self, message):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"\n{message}\n", "user")
        self.chat_display.tag_config("user", foreground="blue", font=("Helvetica", 14, "bold"), lmargin1=40, lmargin2=40)
        self.chat_display.config(state=tk.DISABLED)

    def insert_assistant_message(self, message):
        self.chat_display.config(state=tk.NORMAL)
        if "```python" in message:
            self.insert_code_block(message)
        else:
            self.chat_display.insert(tk.END, f"\n{message}\n", "assistant")
            self.chat_display.tag_config("assistant", foreground="green", font=("Helvetica", 14, "italic"))
        self.chat_display.config(state=tk.DISABLED)

    def insert_code_block(self, message):
        code_block = message.split("```python")[1].split("```")[0]
        self.chat_display.insert(tk.END, "\n", "assistant")
        self.chat_display.insert(tk.END, f"{code_block}\n", "code")
        self.chat_display.tag_config("code", background="#f0f0f0", foreground="black", font=("Courier", 14))

        copy_button = tk.Button(self.chat_frame, text="Copy", command=lambda: pyperclip.copy(code_block))
        self.chat_display.window_create(tk.END, window=copy_button)
        self.chat_display.insert(tk.END, "\n")

    def get_openai_response(self):
        retries = 5
        backoff = 1
        for i in range(retries):
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=self.chat_history
                )
                return completion.choices[0].message.content
            except Exception as e:
                print(f"Rate limit error: {e}. Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
        return "Failed to get a response due to rate limit errors."

    def save_current_conversation(self):
        if self.current_conversation_title is None:
            # No conversation selected, create a new one
            if len(self.chat_history) > 1:
                first_query = self.chat_history[1]["content"]
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an assistant that generates titles for conversations."},
                        {"role": "user", "content": f"Generate a title for a conversation based on this first query: {first_query}"}
                    ],
                    max_tokens=10,
                    temperature=0.5
                )
                title = response.choices[0].message.content.strip()
                self.save_conversation(title)
                self.sidebar.selection_set(self.sidebar.get_children()[-1])
                self.current_conversation_title = title
        else:
            # Save the current conversation
            title = self.current_conversation_title
            self.save_conversation(title)

    def save_conversation(self, title):
        file_path = os.path.join(CONVERSATION_DIR, f"{title}.json")
        with open(file_path, 'w') as file:
            json.dump(self.chat_history, file, indent=2)
        if not self.current_conversation_title:
            self.sidebar.insert("", "end", text=title)
            self.current_conversation_title = title

    def load_conversations(self):
        for file_name in os.listdir(CONVERSATION_DIR):
            if file_name.endswith(".json"):
                self.sidebar.insert("", "end", text=file_name[:-5])

    def show_context_menu(self, event):
        try:
            self.context_menu.selection = self.sidebar.identify_row(event.y)
            self.sidebar.selection_set(self.context_menu.selection)
            self.context_menu.post(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def rename_conversation(self):
        selected_item = self.sidebar.selection()
        if selected_item:
            title = self.sidebar.item(selected_item, "text")
            new_title = simpledialog.askstring("Rename Conversation", "Enter the new title:", initialvalue=title)
            if new_title:
                old_file_path = os.path.join(CONVERSATION_DIR, f"{title}.json")
                new_file_path = os.path.join(CONVERSATION_DIR, f"{new_title}.json")
                os.rename(old_file_path, new_file_path)
                self.sidebar.item(selected_item, text=new_title)
                self.current_conversation_title = new_title

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()
