FROM freqtradeorg/freqtrade:stable

# Install additional dependencies required for FreqAI (datasieve) and our strategy
# Torch CPU build is installed to satisfy PyTorchRegressor without CUDA.
USER root
RUN pip install --no-cache-dir \
    --upgrade pip \
 && pip install --no-cache-dir \
    datasieve \
    scikit-learn \
    lightgbm \
    requests \
    vaderSentiment \
 && true
USER ftuser
