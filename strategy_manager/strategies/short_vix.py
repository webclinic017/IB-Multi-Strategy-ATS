import yfinance as yf
from ib_insync import *
import pandas as pd
import numpy as np
import datetime
from broker.trademanager import TradeManager
from gui.log import add_log, start_event

# TODO: # FINISH STRATEGY
        # Assign callbacks for order updates and code the functions in trade_manager which sends updates to strategy_manager
        # trade.fillEvent += self.trade_manager.on_fill
        # trade.statusEvent += self.trade_manager.on_status_change 

class VRP:
    def __init__(self,ib,strategy_manager,trade_manager):
        self.ib = ib
        self.strategy_manager = strategy_manager
        self.trade_manager = trade_manager

        self.strategy_symbol = "SVRP"
        self.SPY_yfTicker = "^GSPC"
        self.VIX_yfTicker = "^VIX"
        self.instrument_symbol = "VXM"

        # Get Data on Strategy Initialization
        self.term_structure = self.get_vxm_term_structure()
        
        # Equity & Cash Management
        self.equity = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "EquityWithLoanValue")
        self.cash = sum(float(entry.value) for entry in self.ib.accountSummary() if entry.tag == "AvailableFunds")
 
        # Position Management
        self.current_weight = self.check_investment_weight(self,symbol="VXM")
        self.invested = bool(self.current_weight)
        self.min_weight, self.target_weight, self.max_weight = 0.04, 0.07, 0.1
        # self.target_weight, self.min_weight, self.max_weight = hp.get_allocation_allowance(self.strategy_symbol)
       
    @staticmethod
    def check_investment_weight(self, symbol):
        """ Returns the investment weight for the given symbol. """
        try:
            # Sum up the investment value for all positions of the given symbol
            market_value = [pos.marketValue for pos in self.ib.portfolio() if pos.contract.symbol==symbol]
            market_value = market_value[0] if market_value else market_value
 
            if not market_value:
                return 0  # Symbol not found or has no value
 
            # Calculate and return the weight
            weight = (market_value / self.equity)
            return weight
 
        except Exception as e:
            print(f"Error calculating investment weight: {e}")
            return None  # or handle the error as appropriate
 
    def download_vix_and_spy_data(self):
        """ Fetch historical data from Yahoo Finance """
        d = datetime.timedelta(days=120)
        end_date = datetime.date.today()
        start_date = end_date - d
        spx_df = yf.download("^GSPC", start=start_date)
        spx_df['Return'] = (spx_df['Close'] - spx_df['Close'].shift(1)) / spx_df['Close'].shift(1)
        spx_df = spx_df[['Close','Return']]
        spx_df['Realised Volatility'] = spx_df['Return'].rolling(21).std()*np.sqrt(252)*100
   
        vix_df = yf.download("^VIX", start=start_date)
        vix_df['VIX'] = vix_df['Close']
        vix_df = vix_df['VIX']
   
        self.vrp_df = spx_df.merge(vix_df, left_index=True, right_index=True, how='inner')
        self.vrp_df ['VRP'] = self.vrp_df ['VIX'].shift(21) - self.vrp_df ['Realised Volatility']
        #print("Latest Volatility Risk Premium",self.vrp_df.tail())
        return self.vrp_df
 
    def get_vxm_term_structure(self):
        """Returns a DataFrame of the VXM future term structure"""
        today = datetime.datetime.now()

        # Generate contract months for the next 9 maturities
        contract_months = [
            f"{today.year + (today.month + i - 1) // 12}{(today.month + i - 1) % 12 + 1:02}" 
            for i in range(9)
        ]

        # Create Future objects for each contract month
        contracts = [Future("VXM", lastTradeDateOrContractMonth=exp) for exp in contract_months]
        qualified_contracts = self.ib.qualifyContracts(*contracts)

        # Set market data type to delayed frozen data
        self.ib.reqMarketDataType(3)

        # Get the spot rate
        spot_rate_df = self.download_vix_and_spy_data()
        spot_rate = spot_rate_df['VIX'].iloc[-1]

        # Prepare data collection
        futures_data = {
            'Contract': ["VIX Index"] + [contract.localSymbol for contract in qualified_contracts],
            'LastPrice': [spot_rate],
            'DTE': [0],
            'AnnualizedYield': [None]
        }

        for contract in qualified_contracts:
            market_data = self.ib.reqMktData(contract)
            self.ib.sleep(1)  # Wait for the data to be fetched
            last_price = market_data.last if market_data.last > 0 else market_data.bid

            expiration_date = datetime.datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d')
            dte = (expiration_date - today).days

            annualized_yield = None
                #                     if last_price >= spot_rate:
    #                         annualized_yield =((spot_rate / last_price) ** (365 / dte) - 1)
    #                     else:
    #                         annualized_yield = ((last_price  / spot_rate) ** (365 / dte) - 1)
            if dte != 0:
                annualized_yield = ((last_price / spot_rate) ** (365 / dte) - 1) if last_price <= spot_rate else ((spot_rate / last_price) ** (365 / dte) - 1)

            futures_data['LastPrice'].append(last_price)
            futures_data['DTE'].append(dte)
            futures_data['AnnualizedYield'].append(annualized_yield)

        # Convert the dictionary to DataFrame
        self.term_structure = pd.DataFrame(futures_data)
        return self.term_structure
    
    # def get_vxm_term_structure(self):
    #     """Returns a DataFrame of the VXM future term structure"""
    # # Get today's date
    #     today = datetime.datetime.now()
 
    #     # Dictionary to store futures data
    #     futures_data = {
    #         'Contract': [],
    #         'LastPrice': [],
    #         'DTE': [],
    #         'AnnualizedYield': []
    #     }
 
    #     # Set market data type to delayed frozen data
    #     self.ib.reqMarketDataType(3)
 
    #     # Get the spot rate from your function
    #     spot_rate_df = self.download_vix_and_spy_data()
    #     spot_rate = spot_rate_df['VIX'].iloc[-1]  # Latest VIX spot rate

    #     # Add the Spot VIX to the dataframe
    #     futures_data['Contract'].append("VIX Index")
    #     futures_data['LastPrice'].append(spot_rate)
    #     futures_data['DTE'].append(0)
    #     futures_data['AnnualizedYield'].append(None)
        
    #     for i in range(9):  # Next 9 maturities
    #         # Calculate the contract month
    #         month = (today.month + i - 1) % 12 + 1
    #         year = today.year + (today.month + i - 1) // 12
    #         contract_month = f"{year}{month:02}"
 
    #         # Find the futures contract
    #         fut = self.ib.qualifyContracts(Future('VXM', lastTradeDateOrContractMonth=contract_month))
 
    #         if fut:
    #             # Fetch the latest market data
    #             market_data = self.ib.reqMktData(fut[0])
    #             self.ib.sleep(1)  # Wait for the data to be fetched
    #             last_price = market_data.last
    #             if last_price <= 0:
    #                 last_price = market_data.bid
                
    #             # Ensure that we have valid market data
    #             if last_price is not None:
    #                 # Calculate days until expiration
    #                 expiration_date = datetime.datetime.strptime(fut[0].lastTradeDateOrContractMonth, '%Y%m%d')
    #                 dte = (expiration_date - today).days

    #                 if dte==0:
    #                     annualized_yield = None
    #                 else:
    #                     # Calculate annualized yield
    #                     if last_price >= spot_rate:
    #                         annualized_yield =((spot_rate / last_price) ** (365 / dte) - 1)
    #                     else:
    #                         annualized_yield = ((last_price  / spot_rate) ** (365 / dte) - 1)
 
    #                 # Append the data to the dictionary
    #                 futures_data['Contract'].append(fut[0].localSymbol)
    #                 futures_data['LastPrice'].append(last_price)
    #                 futures_data['DTE'].append(dte)
    #                 futures_data['AnnualizedYield'].append(annualized_yield)
 
    #     # Convert the dictionary to DataFrame
    #     self.term_structure = pd.DataFrame(futures_data)
    #     return self.term_structure
 
    def is_contango(self):
        """Returns True if VXM Futures trade in contango, False if in Backwardation"""
        try:
            self.is_contango = self.term_structure['LastPrice'].is_monotonic_increasing
        except:
            self.get_vxm_term_structure()
            self.is_contango = self.term_structure['LastPrice'].is_monotonic_increasing
 
    def calculate_number_of_contracts(self,allocated_amount, contract_price, contract_size):
        """
        Calculate the number of futures contracts to trade based on allocated amount.
 
        Args:
        allocated_amount (float): The dollar amount allocated for the futures contracts.
        contract_price (float): The price of a single futures contract.
        contract_size (float): The size of a single futures contract.
 
        Returns:
        int: The number of futures contracts to trade.
        """
        total_value = contract_price * contract_size
        number_of_contracts = allocated_amount // total_value
        return int(number_of_contracts)
 
    def choose_future_to_short(self):
        """
        Determine which VIX future to short based on the highest yield for futures with a price above 16.
        """

        # Filter out futures with prices below 16
        filtered_futures = self.term_structure[self.term_structure['LastPrice'] > 16]

        # Sort the filtered futures by AnnualizedYield in ascending order (most negative first)
        sorted_futures = filtered_futures.sort_values(by='AnnualizedYield')

        # Select the future with the highest (most negative) yield
        chosen_future = sorted_futures.iloc[0]['Contract'] if not sorted_futures.empty else None

        return chosen_future

    def check_conditions_and_trade(self):
        """ Check the trading conditions and execute trades """
        # Determine optimal Future to short
        symbol_to_short = self.choose_future_to_short()
        contract_to_short = self.ib.qualifyContracts(Future(localSymbol=symbol_to_short))[0]

        if not self.invested:
            if self.vrp_df["VRP"].iloc[-1] > 0:
                self.short_future(contract_to_short)
        else:
            # handle position management when invested
            current_contract = self.get_invested_contract()

            # when another contract has a higher expected yield, roll futures
            if current_contract != contract_to_short:
                self.roll_future(current_contract, contract_to_short)
            
            # Check for a natural roll
            dte = self.get_dte(current_contract)
            if dte <= 5:
                new_contract = self.get_next_contract(current_contract)
                if new_contract:
                    self.trade_manager.roll_future(current_contract, new_contract, orderRef=self.strategy_symbol)
            
            # check if we need to rebalance, because we are out of investment limits
            if self.min_weight < self.current_weight or self.current_weight > self.max_weight:
                allocated_amount = self.equity * self.target_weight
                contract_price = self.get_contract_price(current_contract)
                multiplier = int(current_contract.multiplier)
                target_quantity = self.calculate_number_of_contracts(allocated_amount,contract_price,multiplier)
                invested_quantity = [pos.position for pos in self.ib.portfolio() if pos.contract.localSymbol==current_contract.localSymbol][0]

                rebal_amount = target_quantity - abs(invested_quantity)

                if rebal_amount:
                    print(f"We need to change our positioning by {rebal_amount} contracts")
                    self.trade_manager.trade(self,current_contract,rebal_amount*-1)

    def get_next_contract(self, current_contract):
        """find the next contract"""
        pass

    def get_dte(self,current_contract):
        today = datetime.datetime.now()         
        expiration_date = datetime.datetime.strptime(current_contract.lastTradeDateOrContractMonth, '%Y%m%d')
        dte = (expiration_date - today).days
        return dte

    def short_future(self, contract):
        """ Short a future contract """
        # self, contract, quantity, order_type='MKT', urgency='Patient', orderRef="", limit=None)
        allocated_amount = self.equity * self.target_weight
        if self.cash > allocated_amount:
            contract_price = self.get_contract_price(contract)
            multiplier = int(contract.multiplier)
            quantity = self.calculate_number_of_contracts(allocated_amount,contract_price,multiplier)
            self.trade_manager.trade(self,contract,quantity)
        else:
            add_log(f"Insufficient Cash to run strategy{self.strategy_symbol}")

    def get_invested_contract(self):
        """ Get the current future contract in the portfolio """
        if self.ib.portfolio():
            self.invested_contract = [pos.contract for pos in self.ib.portfolio() if pos.contract.symbol==self.instrument_symbol][0]
            self.ib.qualifyContracts(self.invested_contract)
            return self.invested_contract
        else:
            return None

    def get_contract_price(self,contract):
        market_data = self.ib.reqMktData(contract)
        self.ib.sleep(1)  # Wait for the data to be fetched
        last_price = market_data.last
        if last_price > 0:
            return last_price
        else:
            return market_data.bid

    def roll_future(self, current_contract, new_contract,orderRef=""):
        """
            Roll a futures contract by closing the current contract and opening a new one.

            :param current_contract: The current ib_insync.Contract to be closed.
            :param new_contract: The new ib_insync.Contract to be opened.
            :param orderRef: Reference identifier for the order.
        """
        if self.get_dte(current_contract) < self.get_dte(new_contract):
            self.trade_manager.roll_future(self,current_contract,new_contract,orderRef)
        else:
            add_log("Not allowed to roll future down the curve")

    def close_position(self, contract):
        """ Close the position in the given future contract """
        # Code for closing the position...
