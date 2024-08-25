import tkinter as tk
from tkinter import ttk, scrolledtext
import websocket
import json
import requests
import threading
import argparse


class FiggieClient:
    def __init__(self, master, is_testnet):
        self.master = master
        self.is_testnet = is_testnet
        self.ws = None
        self.inventory = {"spades": 0, "hearts": 0, "diamonds": 0, "clubs": 0}
        self.player_id = ""
        self.player_name = ""
        self.setup_ui()

    def setup_ui(self):
        self.master.title("Figgie Game Client")
        self.master.geometry("600x800")

        if self.is_testnet:
            self.setup_testnet_ui()
        else:
            self.setup_live_ui()

        self.setup_inventory_ui()
        self.setup_order_book_ui()
        self.setup_order_placement_ui()
        self.setup_trade_history_ui()

        self.log_text = scrolledtext.ScrolledText(
            self.master, wrap=tk.WORD, width=90, height=10
        )
        self.log_text.pack(padx=10, pady=10)

        # Add waiting message
        self.waiting_label = ttk.Label(self.master, text="Waiting for round start...")
        self.waiting_label.pack(pady=5)

    def setup_testnet_ui(self):
        frame = ttk.Frame(self.master)
        frame.pack(padx=10, pady=10)

        ttk.Label(frame, text="Player Name:").grid(
            row=0, column=0, sticky="e", padx=5, pady=5
        )
        self.name_entry = ttk.Entry(frame, width=30)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(
            frame,
            text="Register and Connect",
            command=self.register_and_connect_testnet,
        ).grid(row=1, column=0, columnspan=2, pady=10)

    def setup_live_ui(self):
        frame = ttk.Frame(self.master)
        frame.pack(padx=10, pady=10)

        ttk.Label(frame, text="Player ID:").grid(
            row=0, column=0, sticky="e", padx=5, pady=5
        )
        self.player_id_entry = ttk.Entry(frame, width=30)
        self.player_id_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(frame, text="Connect", command=self.connect_live).grid(
            row=1, column=0, columnspan=2, pady=10
        )

    def setup_inventory_ui(self):
        frame = ttk.Frame(self.master)
        frame.pack(padx=10, pady=5)

        self.inventory_labels = {}
        for i, suit in enumerate(["spade", "heart", "diamond", "club"]):
            ttk.Label(frame, text=f"{suit}:").grid(row=0, column=i * 2, padx=5)
            self.inventory_labels[suit.lower() + "s"] = ttk.Label(frame, text="0")
            self.inventory_labels[suit.lower() + "s"].grid(
                row=0, column=i * 2 + 1, padx=5
            )

    def setup_order_book_ui(self):
        frame = ttk.Frame(self.master)
        frame.pack(padx=10, pady=5)

        columns = ("Suit", "Bid Price", "Bid Player", "Ask Price", "Ask Player")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=4)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")

        self.tree.pack(pady=5)

        for suit in ["spades", "hearts", "diamonds", "clubs"]:
            self.tree.insert(
                "", "end", iid=suit.lower(), values=(suit, "-1", "", "-1", "")
            )

    def setup_order_placement_ui(self):
        frame = ttk.Frame(self.master)
        frame.pack(padx=10, pady=5)

        ttk.Label(frame, text="Suit:").grid(row=0, column=0, padx=5, pady=5)
        self.suit_var = tk.StringVar(value="spade")
        self.suit_combo = ttk.Combobox(
            frame,
            textvariable=self.suit_var,
            values=["spade", "heart", "diamond", "club"],
            state="disabled",
        )
        self.suit_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Price:").grid(row=0, column=2, padx=5, pady=5)
        self.price_entry = ttk.Entry(frame, width=10, state="disabled")
        self.price_entry.grid(row=0, column=3, padx=5, pady=5)

        self.order_type = tk.StringVar(value="buy")
        self.buy_radio = ttk.Radiobutton(
            frame, text="Buy", variable=self.order_type, value="buy", state="disabled"
        )
        self.buy_radio.grid(row=0, column=4, padx=5, pady=5)
        self.sell_radio = ttk.Radiobutton(
            frame, text="Sell", variable=self.order_type, value="sell", state="disabled"
        )
        self.sell_radio.grid(row=0, column=5, padx=5, pady=5)

        self.place_order_button = ttk.Button(
            frame, text="Place Order", command=self.place_order, state="disabled"
        )
        self.place_order_button.grid(row=0, column=6, padx=5, pady=5)

        self.cancel_order_button = ttk.Button(
            frame, text="Cancel Order", command=self.cancel_order, state="disabled"
        )
        self.cancel_order_button.grid(row=0, column=7, padx=5, pady=5)

    def setup_trade_history_ui(self):
        frame = ttk.Frame(self.master)
        frame.pack(padx=10, pady=5)

        ttk.Label(frame, text="Trade History:").pack(anchor="w")

        self.trade_history = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, width=90, height=10
        )
        self.trade_history.pack(pady=5)

    def enable_order_controls(self):
        self.suit_combo.config(state="readonly")
        self.price_entry.config(state="normal")
        self.buy_radio.config(state="normal")
        self.sell_radio.config(state="normal")
        self.place_order_button.config(state="normal")
        self.cancel_order_button.config(state="normal")

    def disable_order_controls(self):
        self.suit_combo.config(state="disabled")
        self.price_entry.config(state="disabled")
        self.buy_radio.config(state="disabled")
        self.sell_radio.config(state="disabled")
        self.place_order_button.config(state="disabled")
        self.cancel_order_button.config(state="disabled")

    def log_message(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def set_player_name(self, name):
        self.player_name = name
        self.log_message(f"Player name set to: {self.player_name}")

    def register_and_connect_testnet(self):
        player_id = self.name_entry.get()
        if not player_id:
            self.log_message("Please enter a player name.")
            return

        try:
            response = requests.post(
                "http://testnet.figgiewars.com/register_testnet",
                headers={"Playerid": player_id},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, str):
                data = json.loads(data)
            if data["status"] == "SUCCESS":
                self.player_id = player_id
                self.player_name = (
                    data["message"].split(":")[1].split(".")[0].strip()
                )  # Extract player name from message
                self.log_message(
                    f"Registration successful. Player name: {self.player_name}"
                )
                self.connect_to_websocket(player_id)
            else:
                self.log_message(f"Registration failed: {data['message']}")
        except requests.RequestException as e:
            self.log_message(f"Error during registration: {str(e)}")
        except json.JSONDecodeError as e:
            self.log_message(f"Error parsing registration response: {str(e)}")

    def connect_live(self):
        player_id = self.player_id_entry.get()
        if not player_id:
            self.log_message("Please enter a player ID.")
            return
        self.connect_to_websocket(player_id)

    def connect_to_websocket(self, player_id):
        ws_url = (
            "ws://testnet-ws.figgiewars.com"
            if self.is_testnet
            else "ws://exchange-ws.figgiewars.com"
        )
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=lambda ws: self.on_open(ws, player_id),
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    def on_open(self, ws, player_id):
        self.log_message("WebSocket connection opened")
        subscribe_message = json.dumps({"action": "subscribe", "playerid": player_id})
        ws.send(subscribe_message)
        self.log_message(f"Sent subscription request: {subscribe_message}")

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            self.log_message(f"Received: {json.dumps(data, indent=2)}")
            self.handle_message(data)
        except json.JSONDecodeError:
            self.log_message(f"Received non-JSON message: {message}")
        except Exception as e:
            self.log_message(f"Error handling message: {str(e)}")

    def handle_message(self, data):
        try:
            if data.get("kind") == "dealing_cards":
                self.update_inventory(data["data"])
                self.enable_order_controls()
                self.round_started = True
                self.waiting_label.config(text="Round started!")
                self.log_message("New round started. Cards dealt.")
            elif data.get("kind") == "update":
                self.update_order_book(data["data"])
                self.handle_trade(data["data"].get("trade"))
            elif data.get("kind") == "end_round":
                self.handle_end_round(data["data"])
            elif data.get("kind") == "end_game":
                self.handle_end_game(data["data"])
            elif "status" in data and "message" in data:
                self.log_message(
                    f"Server message: {data['status']} - {data['message']}"
                )
        except Exception as e:
            self.log_message(f"Error in handle_message: {str(e)}")

    def handle_end_round(self, round_data):
        self.disable_order_controls()
        self.round_started = False
        self.waiting_label.config(text="Round ended. Waiting for next round...")

        # Display round results
        self.log_message("\n--- Round Results ---")
        self.log_message(f"Common Suit: {round_data['common_suit']}")
        self.log_message(f"Goal Suit: {round_data['goal_suit']}")

        # Display final card count
        self.log_message("\nFinal Card Count:")
        for suit, count in round_data["card_count"].items():
            self.log_message(f"{suit.capitalize()}: {count}")

        # Display player inventories
        self.log_message("\nPlayer Inventories:")
        for player in round_data["player_inventories"]:
            self.log_message(f"{player['player_name']}: {player}")

        # Display points earned this round
        self.log_message("\nPoints Earned This Round:")
        for player in round_data["player_points"]:
            self.log_message(f"{player['player_name']}: {player['points']}")

        self.log_message("\nWaiting for the next round to start...")

    def handle_end_game(self, game_data):
        self.disable_order_controls()
        self.round_started = False
        self.waiting_label.config(text="Game ended.")

        self.log_message("\n=== Game Over ===")
        self.log_message("Final Standings:")

        # Sort players by points in descending order
        sorted_players = sorted(
            game_data["player_points"], key=lambda x: x["points"], reverse=True
        )

        for i, player in enumerate(sorted_players, 1):
            self.log_message(f"{i}. {player['player_name']}: {player['points']} points")

        self.log_message("\nThank you for playing!")

    def update_inventory(self, inventory_data):
        for suit, count in inventory_data.items():
            self.inventory[suit] = count
            if suit in self.inventory_labels:
                self.inventory_labels[suit].config(text=str(count))
        self.log_message(f"Updated inventory: {self.inventory}")

    def update_order_book(self, book_data):
        for suit, data in book_data.items():
            if suit not in ["spades", "hearts", "diamonds", "clubs"]:
                continue
            bid = data["bids"][0] if data["bids"] else ["-1", ""]
            ask = data["asks"][0] if data["asks"] else ["-1", ""]
            last_trade = data.get("last_trade", "")
            self.tree.item(
                suit,
                values=(suit.capitalize(), bid[0], bid[1], ask[0], ask[1], last_trade),
            )

    def handle_trade(self, trade_data):
        if trade_data:
            card, price, buyer, seller = trade_data.split(",")
            trade_msg = f"Trade: {card} at {price} from {seller} to {buyer}"
            self.log_message(trade_msg)

            # Update trade history
            self.trade_history.insert(tk.END, trade_msg + "\n")
            self.trade_history.see(tk.END)

            # Update inventory based on the trade
            if buyer == self.player_name:
                self.inventory[card + "s"] += 1
            elif seller == self.player_name:
                self.inventory[card + "s"] -= 1

            # Update the inventory display
            if card + "s" in self.inventory_labels:
                self.inventory_labels[card + "s"].config(
                    text=str(self.inventory[card + "s"])
                )

            self.log_message(f"Updated inventory after trade: {self.inventory}")

    def place_order(self):
        suit = self.suit_var.get().lower()
        price = self.price_entry.get()
        direction = self.order_type.get()

        if not price.isdigit():
            self.log_message("Please enter a valid price.")
            return

        order_data = {"card": suit, "price": int(price), "direction": direction}

        try:
            url = (
                "http://testnet.figgiewars.com/order"
                if self.is_testnet
                else "http://exchange.figgiewars.com/order"
            )
            response = requests.post(
                url,
                json=order_data,
                headers={
                    "Playerid": (
                        self.name_entry.get()
                        if self.is_testnet
                        else self.player_id_entry.get()
                    )
                },
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, str):
                data = json.loads(data)
            self.log_message(f"Order placement response: {data['message']}")
        except requests.RequestException as e:
            self.log_message(f"Error placing order: {str(e)}")
        except json.JSONDecodeError as e:
            self.log_message(f"Error parsing order response: {str(e)}")

    def cancel_order(self):
        suit = self.suit_var.get().lower()
        direction = self.order_type.get()

        cancel_data = {"card": suit, "direction": direction}

        try:
            url = (
                "http://testnet.figgiewars.com/cancel"
                if self.is_testnet
                else "http://exchange.figgiewars.com/cancel"
            )
            response = requests.post(
                url,
                json=cancel_data,
                headers={
                    "Playerid": (
                        self.name_entry.get()
                        if self.is_testnet
                        else self.player_id_entry.get()
                    )
                },
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, str):
                data = json.loads(data)
            self.log_message(f"Order cancellation response: {data['message']}")
        except requests.RequestException as e:
            self.log_message(f"Error cancelling order: {str(e)}")
        except json.JSONDecodeError as e:
            self.log_message(f"Error parsing cancellation response: {str(e)}")

    def on_error(self, ws, error):
        self.log_message(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.log_message("WebSocket connection closed")


def main():
    parser = argparse.ArgumentParser(description="Figgie Game Client")
    parser.add_argument("--testnet", action="store_true", help="Connect to testnet")
    args = parser.parse_args()

    root = tk.Tk()
    FiggieClient(root, args.testnet)
    root.mainloop()


if __name__ == "__main__":
    main()
