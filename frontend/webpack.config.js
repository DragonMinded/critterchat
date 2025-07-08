const path = require('path');
var AssetsPlugin = require('assets-webpack-plugin')
var assetsPluginInstance = new AssetsPlugin({
    fullPath: false,
    removeFullPathAutoPrefix: true,
    useCompilerPath: true,
})

module.exports = {
    entry: './src/chat.js',
    output: {
        filename: 'chat.[fullhash].js',
        path: path.resolve(__dirname, '../backend/critterchat/http/static'),
    },
    plugins: [assetsPluginInstance]
};
