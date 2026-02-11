const path = require('path');
var AssetsPlugin = require('assets-webpack-plugin')
var assetsPluginInstance = new AssetsPlugin({
    fullPath: false,
    removeFullPathAutoPrefix: true,
    useCompilerPath: true,
})

module.exports = {
    entry: {
        chat: './src/chat.js',
        home: './src/home.js',
    },
    output: {
        filename: '[name].[fullhash].js',
        path: path.resolve(__dirname, '../backend/critterchat/http/static'),
    },
    plugins: [assetsPluginInstance],
    performance: {
        maxEntrypointSize: 300000,
        maxAssetSize: 300000
    }
};
