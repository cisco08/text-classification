from pathlib import Path

import tensorflow as tf
from numpy import argmax


class TextCNN:
    def __init__(self, tag, learning_rate, num_epochs, sess, dataset_name, seq_length, train_generator,
                 eval_generator, vocabulary_size, num_class, name, checkpoint_dir, embedding_dim, num_filters,
                 kernel_size, keep_pro, save_freq, **kwargs):
        self.kwargs = kwargs
        self.tag = tag
        self.num_epochs = num_epochs
        self.save_freq = save_freq
        self.sess = sess

        self.dataset_name = dataset_name
        self.seq_length = seq_length
        self.train_generator = train_generator
        self.eval_generator = eval_generator
        self.vocabulary_size = vocabulary_size
        self.num_class = num_class

        self.name = name
        self.checkpoint_dir = Path(checkpoint_dir) / self.dataset_name / self.name / self.tag
        self.embedding_dim = embedding_dim
        self.num_filters = num_filters
        self.kernel_size = kernel_size
        self.keep_prob = keep_pro
        self.learning_rate = float(learning_rate)

        self.build_networks()
        self.train_saver = tf.train.Saver()
        self.best_saver = tf.train.Saver()

    def build_networks(self):
        # Input data.
        with tf.name_scope('inputs'):
            self.inputs = tf.placeholder(tf.int32, [None, self.seq_length], name='inputs')
            self.labels = tf.placeholder(tf.float32, [None, self.num_class], name='labels')
            self.keep_prob_tensor = tf.placeholder(tf.float32, name='keep_prob')
        # 词向量映射
        with tf.device('/cpu:0'):
            embedding = tf.get_variable('embedding', [self.vocabulary_size, self.embedding_dim])
            embedding_inputs = tf.nn.embedding_lookup(embedding, self.inputs)

        with tf.name_scope('cnn'):
            # CNN layer
            conv = tf.layers.conv1d(embedding_inputs, self.num_filters, self.kernel_size, name='conv')
            # global max pooling layer
            gmp = tf.reduce_max(conv, reduction_indices=[1], name='gmp')
        with tf.name_scope("score"):
            # 全连接层，后面接dropout以及relu激活
            fc = tf.layers.dense(gmp, self.num_filters // 2, name='fc1')
            fc = tf.contrib.layers.dropout(fc, self.keep_prob_tensor)
            fc = tf.nn.relu(fc)
            # 分类器
            self.logits = tf.layers.dense(fc, self.num_class, name='fc2')
            self.target = tf.argmax(tf.nn.softmax(self.logits), 1)  # 预测类别
        with tf.name_scope('loss'):
            self.loss = tf.reduce_mean(
                tf.nn.softmax_cross_entropy_with_logits_v2(logits=self.logits, labels=self.labels))
        with tf.name_scope('accuracy'):
            correct_pred = tf.equal(tf.argmax(self.labels, 1), self.target)
            self.accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

        with tf.name_scope('tensorboard'):
            loss_scalar = tf.summary.scalar('train_loss', self.loss)
            accuracy_scalar = tf.summary.scalar('train_accuracy', self.accuracy)
            self.eval_loss = tf.placeholder(tf.float32, name='eval_loss')
            eval_loss_scalar = tf.summary.scalar('loss', self.eval_loss)
            self.eval_accuracy = tf.placeholder(tf.float32, name='eval_accuracy')
            eval_accuracy_scalar = tf.summary.scalar('accuracy', self.eval_accuracy)
            self.scalar_summary = tf.summary.merge(
                [loss_scalar, accuracy_scalar, eval_loss_scalar, eval_accuracy_scalar])

    def train(self):
        optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)
        init_op = tf.global_variables_initializer()
        self.sess.run(init_op)
        writer = tf.summary.FileWriter('../tensorboard_logs/{}/{}/{}'.format(self.dataset_name, self.name, self.tag),
                                       self.sess.graph)
        best_glob_accuracy = 0
        train_size = self.train_generator.get_size()
        eval_size = self.eval_generator.get_size()
        print('开始训练')
        for epoch in range(self.num_epochs):
            train_loss = 0
            train_accuracy = 0
            for step in range(train_size):
                batch_inputs, batch_labels = next(self.train_generator.get_data_generator())
                _, loss, accuracy = self.sess.run([optimizer, self.loss, self.accuracy],
                                                  feed_dict={self.inputs: batch_inputs, self.labels: batch_labels,
                                                             self.keep_prob_tensor: self.keep_prob})
                train_loss += loss
                train_accuracy += accuracy
            # 开始验证结果
            eval_loss = 0
            eval_accuracy = 0
            for step in range(eval_size):
                batch_inputs, batch_labels = next(self.eval_generator.get_data_generator())
                loss, accuracy = self.sess.run([self.loss, self.accuracy],
                                               feed_dict={self.inputs: batch_inputs, self.labels: batch_labels,
                                                          self.keep_prob_tensor: 1.0})
                eval_loss += loss
                eval_accuracy += accuracy
            print('第{}轮训练：train_loss:{},train_accuracy:{},eval_loss:{},eval_accuracy:{}'
                  .format(epoch + 1, train_loss / train_size, train_accuracy / train_size, eval_loss / eval_size,
                          eval_accuracy / eval_size))
            summary = self.sess.run(self.scalar_summary,
                                    feed_dict={self.loss: train_loss / train_size,
                                               self.accuracy: train_accuracy / train_size,
                                               self.eval_loss: eval_loss / eval_size,
                                               self.eval_accuracy: eval_accuracy / eval_size})
            writer.add_summary(summary, epoch)
            # save train model
            if epoch % self.save_freq == 0:
                self.save(self.checkpoint_dir / 'train', self.train_saver, epoch)
            if best_glob_accuracy < (train_accuracy + eval_accuracy):
                self.save(self.checkpoint_dir / 'best', self.best_saver, epoch)
                best_glob_accuracy = train_accuracy + eval_accuracy

    def test(self):
        init_op = tf.global_variables_initializer()
        self.sess.run(init_op)
        self.load(self.checkpoint_dir / 'best', self.best_saver)
        eval_size = self.eval_generator.get_size()
        batch_size = self.eval_generator.get_batch_size()
        result = list()
        print('开始测试')
        for step in range(eval_size):
            batch_inputs, batch_labels = next(self.eval_generator.get_data_generator())
            loss, accuracy, pre_labels = self.sess.run([self.loss, self.accuracy, self.target],
                                                       feed_dict={self.inputs: batch_inputs, self.labels: batch_labels,
                                                                  self.keep_prob_tensor: 1.0})
            batch_result = list()
            for i in range(batch_size):
                label_id = argmax(batch_labels[i])
                batch_result.append({'_预测的分类': str(self.eval_generator.get_label(pre_labels[i])),
                                     '_实际的分类': str(self.eval_generator.get_label(label_id)),
                                     '输入的文字': str(self.eval_generator.get_words(batch_inputs[i]))})
            result.append({'loss': float(loss), 'accuracy': float(accuracy), '训练的结果': batch_result})
            print('{}/{} loss:{} accuracy:{}'.format(step + 1, eval_size, loss, accuracy))
        return result

    def save(self, checkpoint_dir, saver, epoch, **kwargs):
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        saver.save(self.sess, str(checkpoint_dir / 'model.cpk'), global_step=epoch)

    def load(self, checkpoint_dir, saver, **kwargs):
        # checkpoint = tf.train.get_checkpoint_state(str(checkpoint_dir))
        checkpoint = tf.train.latest_checkpoint(str(checkpoint_dir))
        if checkpoint:
            # saver.restore(self.sess, checkpoint.model_checkpoint_path)
            saver.restore(self.sess, checkpoint)
        else:
            print('Loading checkpoint failed')
