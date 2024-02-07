import tkinter as tk
from tkinter import ttk
import pandas as pd
from datetime import datetime
from data_and_research import ac, fetch_strategies

def on_combobox_select(tree, strategy, row_id):
    # Get the symbol from the row
    symbol = tree.set(row_id, 'symbol')
    row = tree.item(row_id)
    
    print(f"Selected Strategy: {strategy}, Row data: {row}")

def open_portfolio_window(strategy_manager):
    window = tk.Toplevel()
    window.title("Portfolio")
    window.geometry("800x400")

    # Fetch the account values
    cash = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "TotalCashValue")
    total_equity = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "EquityWithLoanValue")
    margin = sum(float(entry.value) for entry in strategy_manager.ib_client.accountSummary() if entry.tag == "InitMarginReq")

    # Create a frame for account information
    account_info_frame = tk.Frame(window)
    account_info_frame.pack(side=tk.BOTTOM, fill=tk.X)

    # Labels for account information
    tk.Label(account_info_frame, text=f"NAV: {total_equity:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f"  Cash: {cash:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f"  Margin: {margin:.2f}").pack(side=tk.LEFT)
    tk.Label(account_info_frame, text=f"Date: {datetime.now().strftime('%Y-%m-%d')}").pack(side=tk.RIGHT)

    portfolio_data = get_portfolio_data(strategy_manager)  # Fetch the data
    df = pd.DataFrame(portfolio_data)
    strategies,_ = fetch_strategies()  # Fetch list of strategies
    strategies.append("")

    # Add a scrollbar
    scrollbar = tk.Scrollbar(window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Create the treeview
    columns = ("symbol", "Asset Class", "position", "FX" ,"Weight (%)",'Price','Cost','pnl %',"strategy")
    tree = ttk.Treeview(window, columns=columns, show='headings', yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Define the column headings
    for col,w in zip(columns,[50,120,60,50,60,60,60,60,100]):
        tree.column(col, stretch=tk.YES, minwidth=0, width=w)  # Adjust the width as needed
        tree.heading(col, text=col.capitalize())

    # Adding data to the treeview
    for item in portfolio_data:
        row_id = tree.insert("", tk.END, values=(item["symbol"], item["asset class"], item["position"], item['currency'],f"{item['% of nav']:.2f}",
                            f"{item['marketPrice']:.2f}", f"{item['averageCost']:.2f}", f"{item['pnl %']:.2f}",item['strategy']))

    # Add a strategy dropdown for each row in a separate column
    def on_strategy_cell_click(event, strategies, df):
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            row_id = tree.identify_row(event.y)
            if tree.heading(column, "text").lower() == "strategy":
                # Get the symbol, asset class, and position from the treeview item
                symbol = tree.set(row_id, 'symbol')
                asset_class = tree.set(row_id, 'Asset Class')
                position = float(tree.set(row_id, 'position'))

                # Find the corresponding dataframe row based on symbol, asset class, and position
                df_row = df[(df['symbol'] == symbol) & 
                            (df['asset class'] == asset_class) & 
                            (df['position'] == position)]
                print(df_row)
                # If no matching row found in the dataframe, set current_strategy to empty
                if df_row.empty:
                    current_strategy = ''
                else:
                    current_strategy = df_row['strategy'].iloc[0]

                # Position the combobox
                x, y, width, height = tree.bbox(row_id, column)
                pady = height // 2
                
                # Create the Combobox widget
                strategy_cb = ttk.Combobox(window, values=strategies)
                strategy_cb.place(x=x, y=y+pady, anchor="w", width=width)
                strategy_cb.set(current_strategy)

                # Bind the selection event
                strategy_cb.bind("<<ComboboxSelected>>", lambda e: on_combobox_select(tree, strategy_cb.get(), row_id))

    def on_right_click(event, tree, df):
        # Identify the row and column that was clicked
        region = tree.identify("region", event.x, event.y)

        
        if region == "cell":
            row_id = tree.identify_row(event.y)
            symbol = tree.set(row_id, 'symbol')
            asset_class = tree.set(row_id, 'Asset Class')
            position = float(tree.set(row_id, 'position'))

            menu = tk.Menu(window, tearoff=0)
            # Add a non-clickable menu entry as a title/header
            menu.add_command(label=f"{asset_class}: {position} {symbol}", state="disabled")
            menu.add_command(label="Delete Entry",command=lambda: delete_strategy(tree, row_id, df))
            menu.post(event.x_root, event.y_root)

    window.update_idletasks()  # Update the GUI to ensure treeview is drawn
    tree.bind("<Button-1>", lambda e: on_strategy_cell_click(e, strategies, df))
    tree.bind("<Button-3>", lambda e: on_right_click(e, tree, df))  # <Button-3> is typically the right-click button
    tree.bind("<Button-2>", lambda e: on_right_click(e, tree, df))

    scrollbar.config(command=tree.yview)

def delete_strategy(tree, row_id, df):
    # Here you would handle the deletion of the strategy entry from the database
    symbol = tree.set(row_id, 'symbol')
    asset_class = tree.set(row_id, 'Asset Class')
    position = tree.set(row_id,'position')

    print(symbol, asset_class, "deleting")

    lib = ac.get_library('portfolio')
    df = lib.read('positions').data
    latest_positions = df.sort_values(by='timestamp').groupby(['symbol', 'strategy', 'asset class']).last().reset_index()
    
    # ...perform deletion from ArcticDB using symbol and asset class as keys

def get_portfolio_data(strategy_manager):
    df = strategy_manager.portfolio_manager.get_ib_positions_for_gui()
    data_list = df.to_dict('records')
    # print(data_list)
    return data_list

def get_strategies(arctic_lib):
    # Fetch list of strategies from ArcticDB
    pass

def assign_strategy(item_id, strategy):
    print(f"from assign_strategy func: {item_id}")
    # Function to assign a strategy to a portfolio item and update in ArcticDB
    pass
