import numpy as np
from utils import yaml_utils


class OneFileDataGenerator:
    def __init__(self, dictionary, is_augmented, dataset_list, batch_size, seq_length, **kwargs):
        self.word_dictionary = dictionary['word_dictionary']
        self.label_dictionary = dictionary['label_dictionary']
        self.is_augmented = is_augmented
        self.dataset_list = dataset_list
        self.batch_size = batch_size
        self.seq_length = seq_length
        self.kwargs = kwargs
        self.transform_word()

    def get_labels(self):
        return [x for x in self.label_dictionary]

    def get_reverse_dictionary(self):
        reverse_dictionary = self.kwargs['reverse_dictionary']
        self.reverse_dictionary = reverse_dictionary['word_dictionary']
        self.reverse_label_dictionary = reverse_dictionary['label_dictionary']

    def get_size(self):
        return len(self.dataset_list) // self.batch_size

    def get_label(self, label_id):
        return self.reverse_label_dictionary[label_id]

    def get_words(self, word_ids):
        result = ''
        for i in word_ids:
            if i == 0:
                continue
            result += self.reverse_dictionary[i]
        return result

    def get_batch_size(self):
        return self.batch_size

    def transform_word(self):
        print('翻译文字成序列')
        for i in range(len(self.dataset_list)):
            # 固定文本序列长度
            input = [self.word_dictionary[x.lower()] for x in self.dataset_list[i]['input'] if
                     x.lower() in self.word_dictionary]
            if len(input) < self.seq_length:
                input.extend([0 for _ in range(self.seq_length - len(input))])
            else:
                input = input[0:self.seq_length]
            self.dataset_list[i]['input'] = input
            # one-hot 处理
            label_id = self.label_dictionary[self.dataset_list[i]['label']]
            label = np.zeros((len(self.label_dictionary)), dtype=np.float32)
            label[label_id] = 1.0
            self.dataset_list[i]['label'] = label
        print('翻译完成')

    def get_data_generator(self):
        batch_input = list()
        batch_label = list()
        while True:
            if self.is_augmented:
                np.random.shuffle(self.dataset_list)
            for item in self.dataset_list:
                batch_input.append(item['input'])
                batch_label.append(item['label'])
                if len(batch_input) == self.batch_size:
                    yield np.array(batch_input), np.array(batch_label)
                    batch_input = list()
                    batch_label = list()


# 测试用
class DataGenerator2:
    def get_size(self):
        return 1

    def get_data_generator(self):
        yield [[0 for _ in range(600)]], [[0 for _ in range(10)]]


if __name__ == '__main__':
    dataset_info = yaml_utils.read('../dataset/cnews/info.yaml')
    dictionary = yaml_utils.read(dataset_info['dictionary_path'])
    train_dataset = yaml_utils.read(dataset_info['eval_path'])
    print('读取完毕')
    data_generator = OneFileDataGenerator(dictionary, True, train_dataset, 32, 600)
    batch_input, batch_label = next(data_generator.get_data_generator())
