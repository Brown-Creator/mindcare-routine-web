"""
딥러닝 시계열 예측 (LSTM 기반)
- 가격 시계열 패턴 인식
- 다변량 LSTM (가격 + 피처)
- Attention 메커니즘
- 앙상블과 통합
"""
import numpy as np
import pandas as pd
from typing import Optional, Tuple
from dataclasses import dataclass
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class DeepPrediction:
    ticker: str
    predicted_direction: str = "중립"
    predicted_return_pct: float = 0
    confidence: float = 0
    sequence_pattern: str = ""

class DeepPredictor:
    """
    LSTM 기반 시계열 예측
    PyTorch 또는 순수 numpy로 간이 구현 (의존성 최소화)
    """

    def __init__(self, seq_length: int = 30, model_dir: str = "data/models"):
        self.seq_length = seq_length
        self.model_dir = Path(model_dir)
        self._model = None
        self._scaler_params = {}
        self._is_trained = False

    def prepare_sequences(self, df: pd.DataFrame,
                          feature_cols: list = None,
                          target_col: str = 'return_5d') -> Tuple:
        """시계열 시퀀스 생성"""
        if feature_cols is None:
            feature_cols = ['close', 'volume', 'rsi_14', 'macd_hist',
                          'bb_pctb', 'vol_ratio_5d']

        available_cols = [c for c in feature_cols if c in df.columns]
        if not available_cols:
            return None, None

        data = df[available_cols].fillna(method='ffill').fillna(0)

        # MinMax 정규화
        self._scaler_params = {
            col: {"min": float(data[col].min()), "max": float(data[col].max())}
            for col in available_cols
        }
        for col in available_cols:
            rng = self._scaler_params[col]["max"] - self._scaler_params[col]["min"]
            if rng > 0:
                data[col] = (data[col] - self._scaler_params[col]["min"]) / rng

        # 타겟 생성
        if target_col in df.columns:
            target = (df[target_col] > 0).astype(int)
        else:
            target = (df['close'].pct_change(5).shift(-5) > 0).astype(int)

        # 시퀀스 생성
        X, y = [], []
        values = data.values
        target_values = target.values
        for i in range(self.seq_length, len(values) - 5):
            X.append(values[i - self.seq_length:i])
            y.append(target_values[i])

        return np.array(X), np.array(y)

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """
        LSTM 학습 (PyTorch)
        PyTorch 미설치 시 sklearn MLP로 대체
        """
        if X is None or len(X) < 100:
            return {"error": "insufficient_data"}

        # 시계열 분할
        split = int(len(X) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]

        try:
            import torch
            import torch.nn as nn
            return self._train_pytorch(X_train, y_train, X_val, y_val)
        except ImportError:
            logger.info("PyTorch 미설치, sklearn MLP로 대체")
            return self._train_sklearn(X_train, y_train, X_val, y_val)

    def _train_sklearn(self, X_train, y_train, X_val, y_val) -> dict:
        """sklearn MLP 대체 학습"""
        try:
            from sklearn.neural_network import MLPClassifier
            # 시퀀스를 플래튼
            X_tr_flat = X_train.reshape(len(X_train), -1)
            X_vl_flat = X_val.reshape(len(X_val), -1)

            model = MLPClassifier(
                hidden_layer_sizes=(128, 64, 32),
                max_iter=200, random_state=42,
                early_stopping=True, validation_fraction=0.15,
            )
            model.fit(X_tr_flat, y_train)
            val_acc = (model.predict(X_vl_flat) == y_val).mean()
            self._model = model
            self._is_trained = True
            logger.info(f"MLP 학습 완료 - 검증 정확도: {val_acc:.2%}")
            return {"model": "MLP", "val_accuracy": round(val_acc, 4)}
        except Exception as e:
            logger.error(f"MLP 학습 실패: {e}")
            return {"error": str(e)}

    def _train_pytorch(self, X_train, y_train, X_val, y_val) -> dict:
        """PyTorch LSTM 학습"""
        import torch
        import torch.nn as nn

        class LSTMModel(nn.Module):
            def __init__(self, input_size, hidden_size=64, num_layers=2):
                super().__init__()
                self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                                   batch_first=True, dropout=0.3)
                self.attention = nn.Linear(hidden_size, 1)
                self.fc = nn.Sequential(
                    nn.Linear(hidden_size, 32),
                    nn.ReLU(), nn.Dropout(0.2),
                    nn.Linear(32, 1), nn.Sigmoid()
                )

            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                # Attention
                attn_weights = torch.softmax(self.attention(lstm_out), dim=1)
                context = (lstm_out * attn_weights).sum(dim=1)
                return self.fc(context).squeeze()

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        input_size = X_train.shape[2]
        model = LSTMModel(input_size).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.BCELoss()

        X_t = torch.FloatTensor(X_train).to(device)
        y_t = torch.FloatTensor(y_train).to(device)
        X_v = torch.FloatTensor(X_val).to(device)
        y_v = torch.FloatTensor(y_val).to(device)

        best_val_acc = 0
        for epoch in range(50):
            model.train()
            optimizer.zero_grad()
            pred = model(X_t)
            loss = criterion(pred, y_t)
            loss.backward()
            optimizer.step()

            model.eval()
            with torch.no_grad():
                val_pred = model(X_v)
                val_acc = ((val_pred > 0.5).float() == y_v).float().mean().item()
                best_val_acc = max(best_val_acc, val_acc)

        self._model = model
        self._is_trained = True
        logger.info(f"LSTM 학습 완료 - 최고 검증 정확도: {best_val_acc:.2%}")
        return {"model": "LSTM", "val_accuracy": round(best_val_acc, 4)}

    def predict(self, X: np.ndarray, ticker: str = "") -> DeepPrediction:
        """예측"""
        if not self._is_trained or self._model is None:
            return DeepPrediction(ticker=ticker, confidence=0)

        try:
            # 마지막 시퀀스만 사용
            if len(X.shape) == 3:
                last_seq = X[-1:]
            else:
                last_seq = X[-1:].reshape(1, -1)

            try:
                import torch
                if isinstance(self._model, torch.nn.Module):
                    self._model.eval()
                    with torch.no_grad():
                        inp = torch.FloatTensor(last_seq)
                        prob = self._model(inp).item()
                else:
                    flat = last_seq.reshape(1, -1) if len(last_seq.shape) > 2 else last_seq
                    prob = self._model.predict_proba(flat)[0][1]
            except ImportError:
                flat = last_seq.reshape(1, -1) if len(last_seq.shape) > 2 else last_seq
                prob = self._model.predict_proba(flat)[0][1]

            direction = "상승" if prob > 0.55 else ("하락" if prob < 0.45 else "중립")
            conf = abs(prob - 0.5) * 2

            return DeepPrediction(
                ticker=ticker,
                predicted_direction=direction,
                predicted_return_pct=round((prob - 0.5) * 10, 2),
                confidence=round(conf, 3),
                sequence_pattern=self._detect_pattern(X),
            )
        except Exception as e:
            logger.error(f"딥러닝 예측 실패: {e}")
            return DeepPrediction(ticker=ticker, confidence=0)

    def _detect_pattern(self, X: np.ndarray) -> str:
        """시퀀스 패턴 감지 (간이)"""
        if len(X) < 2:
            return "불명"
        prices = X[-self.seq_length:, 0] if len(X.shape) > 1 else X[-self.seq_length:]
        if len(prices) < 10:
            return "불명"

        first_half = prices[:len(prices)//2].mean()
        second_half = prices[len(prices)//2:].mean()
        last_5 = prices[-5:].mean()

        if second_half > first_half * 1.03 and last_5 > second_half:
            return "상승추세 가속"
        elif second_half < first_half * 0.97 and last_5 < second_half:
            return "하락추세 가속"
        elif second_half < first_half * 0.95 and last_5 > second_half * 1.01:
            return "V자 반등"
        elif second_half > first_half * 1.05 and last_5 < second_half * 0.99:
            return "고점 후 조정"
        else:
            return "횡보"
