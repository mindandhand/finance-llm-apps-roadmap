"""使用 Qlib DatasetH 和 LightGBM 完成一个最小训练、预测与 IC 评估流程。"""

from pathlib import Path
import sys

# 允许直接在当前子目录运行脚本时导入仓库根目录的公共工具。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import (
    end_time,
    init_qlib,
    instruments,
    print_context,
    start_time,
    test_start_time,
    train_end_time,
    valid_end_time,
    valid_start_time,
)


# 所有特征只引用当前或历史数据，避免把未来信息泄漏给模型。
FEATURE_FIELDS = [
    "$close / Ref($close, 5) - 1",  # 5 日价格动量
    "$close / Ref($close, 20) - 1",  # 20 日价格动量
    "Std($close / Ref($close, 1) - 1, 20)",  # 日收益率的 20 日滚动标准差
    "Mean($volume, 5) / Mean($volume, 20)",  # 短期与中期平均成交量之比
]
FEATURE_NAMES = ["MOM5", "MOM20", "RETURN_VOLATILITY_20", "VOLUME_RATIO_5_20"]

# 负数 Ref 表示引用未来：标签是 t+1 到 t+2 两个未来时点之间的收益率。
LABEL_FIELDS = ["Ref($close, -2) / Ref($close, -1) - 1"]
LABEL_NAMES = ["LABEL0"]


def build_dataset():
    """构造包含特征、标签、处理器及训练/测试时间段的 Qlib 数据集。"""
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.handler import DataHandlerLP

    # DataHandlerLP 管理 raw、infer 和 learn 三种数据视图。
    handler = DataHandlerLP(
        instruments=instruments(),
        start_time=start_time(),
        end_time=end_time(),
        data_loader={
            # QlibDataLoader 把表达式交给 Qlib 数据层批量计算。
            "class": "QlibDataLoader",
            "kwargs": {
                "config": {
                    "feature": (FEATURE_FIELDS, FEATURE_NAMES),
                    "label": (LABEL_FIELDS, LABEL_NAMES),
                }
            },
        },
        learn_processors=[
            # 训练视图删除无标签样本，并填补特征缺失值。
            {"class": "DropnaLabel"},
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
        ],
    )

    # segment 是时间切片；它和 handler 的 learn/infer 数据视图是两个维度。
    return DatasetH(
        handler=handler,
        segments={
            "train": (start_time(), train_end_time()),
            "valid": (valid_start_time(), valid_end_time()),
            "test": (test_start_time(), end_time()),
        },
    )


def main() -> None:
    # 必须先初始化 provider，DataHandler 才能解析表达式并读取行情数据。
    init_qlib()
    print_context("Qlib model training baseline")

    from qlib.contrib.model.gbdt import LGBModel
    from qlib.data.dataset.handler import DataHandlerLP

    dataset = build_dataset()

    # LGBModel 是 Qlib 对 LightGBM 回归模型的封装，目标是拟合未来收益标签。
    model = LGBModel(
        loss="mse",
        learning_rate=0.05,
        num_leaves=32,
        max_depth=6,
        num_threads=4,
    )
    model.fit(dataset)

    # 只对 test segment 生成样本外分数，避免把训练期表现当成泛化能力。
    # pred 是以 (datetime, instrument) 为索引的 Series；由于模型使用 MSE
    # 拟合收益率标签，其值可理解为预测收益，也常被当作标的排序分数。
    pred = model.predict(dataset, segment="test")

    # 读取同一 test 时间段的真实未来收益：
    # - col_set="label" 只选择标签列；
    # - DK_L 选择经过 learn_processors 处理的数据视图；
    # - iloc[:, 0] 把单列 DataFrame 转为 Series。
    label = dataset.prepare(
        "test",
        col_set="label",
        data_key=DataHandlerLP.DK_L,
    ).iloc[:, 0]

    # pred 和 label 具有相同的 (datetime, instrument) 索引。
    # inner join 只保留两边都存在的样本，dropna 再删除预测或标签缺失的行。
    joined = (
        pred.rename("score")
        .to_frame()
        .join(label.rename("label"), how="inner")
        .dropna()
    )

    # 按日期切出当天所有标的，在横截面上计算预测分数和真实收益的 Pearson IC。
    # daily_ic 的每个值对应一个交易日；后面的 mean() 再衡量整个测试期的平均 IC。
    # 这不是分类准确率或策略收益，而是模型横截面选股能力的统计指标。
    daily_ic = joined.groupby(level="datetime").apply(
        lambda group: group["score"].corr(group["label"])
    )

    print("prediction rows:", len(pred))
    print("mean test IC:", round(float(daily_ic.mean()), 6))
    print(joined.head(20).to_string())


if __name__ == "__main__":
    main()
