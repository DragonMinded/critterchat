const path = require('path');
const webpack = require('webpack');
const AssetsPlugin = require('assets-webpack-plugin')

module.exports = {
    entry: {
        chat: './src/chat.js',
        home: './src/home.js',
    },
    output: {
        filename: '[name].[fullhash].js',
        path: path.resolve(__dirname, '../backend/critterchat/http/static'),
    },
    plugins: [
        new AssetsPlugin({
            fullPath: false,
            removeFullPathAutoPrefix: true,
            useCompilerPath: true,
        }),
        new webpack.ContextReplacementPlugin(
            /highlight\.js\/lib\/languages$/,
            new RegExp(`^./(${['python', 'css', 'xml', 'javascript', 'c', 'cpp', 'ini', 'yaml', 'json', 'php', 'rust', 'java'].join('|')})$`),
        ),
    ],
    performance: {
        maxEntrypointSize: 300000,
        maxAssetSize: 300000
    }
};
