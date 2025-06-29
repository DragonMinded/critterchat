const path = require('path');

module.exports = {
    entry: './src/chat.js',
    output: {
        filename: 'chat.js',
        path: path.resolve(__dirname, '../backend/federateddergchat/http/static'),
    },
};
