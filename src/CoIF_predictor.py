import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ============================================================
# 1. LOAD DATASET
# ============================================================

FILE_NAME = "coif_training_history_1.csv"

df = pd.read_csv(FILE_NAME)

print("\n========== DATASET ==========")
print(df.head())

print("\nDataset shape:")
print(df.shape)

print("\nColumns:")
print(df.columns.tolist())


# ============================================================
# 2. DEFINE INPUT PARAMETERS AND TARGET
# ============================================================

features = [
    "priority_weight",
    "process_impact_weight",
    "frequency",
    "close_calendar_multiplier"
]

target = "CoIF"


# Check whether columns exist
for column in features + [target]:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found in CSV. "
            f"Available columns: {df.columns.tolist()}"
        )


# ============================================================
# 3. PREPARE DATA
# ============================================================

X = df[features]
y = df[target]

print("\n========== INPUT FEATURES ==========")
print(X.head())

print("\n========== TARGET ==========")
print(y.head())


# ============================================================
# 4. TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)


# ============================================================
# 5. TRAIN LINEAR REGRESSION MODEL
# ============================================================

model = LinearRegression()

model.fit(X_train, y_train)


# ============================================================
# 6. GET LEARNED WEIGHTS
# ============================================================

print("\n\n========================================")
print("        LEARNED COIF WEIGHTS")
print("========================================")

for feature, weight in zip(features, model.coef_):
    print(f"{feature:30s} : {weight:.6f}")

print("----------------------------------------")
print(f"{'Intercept':30s} : {model.intercept_:.6f}")


# ============================================================
# 7. DISPLAY FORMULA
# ============================================================

print("\n\n========================================")
print("          LEARNED COIF FORMULA")
print("========================================")

print(
    f"CoIF = {model.intercept_:.6f}"
    f" + ({model.coef_[0]:.6f} * priority_weight)"
    f" + ({model.coef_[1]:.6f} * process_impact_weight)"
    f" + ({model.coef_[2]:.6f} * frequency)"
    f" + ({model.coef_[3]:.6f} * close_calendar_multiplier)"
)


# ============================================================
# 8. PREDICTION ON TEST DATA
# ============================================================

y_pred = model.predict(X_test)


# ============================================================
# 9. MODEL EVALUATION
# ============================================================

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\n\n========================================")
print("          MODEL PERFORMANCE")
print("========================================")

print(f"R² Score : {r2:.4f}")
print(f"MAE      : {mae:.4f}")
print(f"RMSE     : {rmse:.4f}")


# ============================================================
# 10. COMPARE ACTUAL VS PREDICTED
# ============================================================

results = pd.DataFrame({
    "Actual CoIF": y_test.values,
    "Predicted CoIF": y_pred
})

results["Error"] = results["Actual CoIF"] - results["Predicted CoIF"]

print("\n\n========================================")
print("       ACTUAL VS PREDICTED")
print("========================================")

print(results.head(20).to_string(index=False))


# ============================================================
# 11. PREDICT COIF FOR A NEW RECORD
# ============================================================

new_data = pd.DataFrame({
    "priority_weight": [80],
    "process_impact_weight": [70],
    "frequency": [5],
    "close_calendar_multiplier": [1.5]
})

predicted_coif = model.predict(new_data)[0]

print("\n\n========================================")
print("        NEW COIF PREDICTION")
print("========================================")

print("Input:")
print(new_data.to_string(index=False))

print(f"\nPredicted CoIF = {predicted_coif:.4f}")


# ============================================================
# 12. SHOW WEIGHTS IN A TABLE
# ============================================================

weights = pd.DataFrame({
    "Parameter": features,
    "Learned Weight": model.coef_
})

print("\n\n========================================")
print("             WEIGHTS")
print("========================================")

print(weights.to_string(index=False))