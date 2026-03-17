from abc import ABC, abstractmethod

class BaseBroker(ABC):
    """
    証券会社（またはシミュレータ）の抽象基底クラス。
    本番のAPI運用に移行する際は、このクラスを継承して各API用のBrokerを作成します。
    """
    
    @abstractmethod
    def get_account_balance(self) -> dict:
        """
        現在の口座残高等を取得します。
        戻り値の例: {"cash": 1000000}
        """
        pass

    @abstractmethod
    def get_positions(self) -> list:
        """
        現在の保有ポジション一覧を取得します。
        戻り値の例: [{"code": "1234", "name": "XXX", "shares": 100, "buy_price": 1000, ...}]
        """
        pass

    @abstractmethod
    def save_positions(self, portfolio: list):
        """
        ポジション情報を保存します（シミュレーション用。本番APIでは不要な場合がありますが互換性のために用意）。
        """
        pass

    @abstractmethod
    def save_account(self, account: dict):
        """
        口座情報を保存します（シミュレーション用）。
        """
        pass

    @abstractmethod
    def log_trade(self, trade_record: dict):
        """
        決済完了したトレード履歴を保存します。
        """
        pass

    @abstractmethod
    def log_execution_summary(self, summary_record: dict):
        """
        毎回の実行サマリー（資産推移）を記録します。
        """
        pass

    @abstractmethod
    def execute_market_order(self, code: str, shares: int, side: str) -> str:
        """
        現物の成行注文を発注し、注文ID（またはシミュレーションID）を返します。
        """
        pass
        
